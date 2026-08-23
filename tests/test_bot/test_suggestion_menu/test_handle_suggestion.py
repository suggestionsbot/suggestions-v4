from typing import cast
from unittest.mock import AsyncMock

import hikari
import lightbulb
import pytest
from freezegun import freeze_time

from bot import utils
from bot.constants import ErrorCode
from bot.localisation import Localisation
from bot.menus import SuggestionMenu
from bot.tables import InternalErrors, MessageAddons, PossibleMessageAddons
from shared.tables import GuildConfigs, Suggestions, UserConfigs
from shared.utils import autocomplete, configs

USER_ID = 12345
GUILD_ID = 23456
CHANNEL_ID = 348934
MESSAGE_ID = 555666
THREAD_ID = 777888
DISPLAY_NAME = f"Skelmis (<@{USER_ID}>)"

CHANNEL_NOT_FOUND_TITLE = "Command Failed"
CHANNEL_NOT_FOUND_DESCRIPTION = (
    "This command requires a queue channel to use.\n"
    "Please contact an administrator and ask them to set one up "
    "using the following command.\n`/configure guild`"
)
MISSING_SEND_PERMS_TITLE = "Command Failed"
MISSING_SEND_PERMS_DESCRIPTION = (
    "The bot does not have permissions to interact with the suggestions channel.\n"
    "Please contact an administrator and ask them to ensure the channel exists "
    "and that the bot can see it/send messages to it."
)
THREAD_NAME_TOO_LONG_TITLE = "Command Failed"
THREAD_NAME_TOO_LONG_DESCRIPTION = "The thread name must be between 1 and 100 in length."
MISSING_THREAD_PERMS_TITLE = "Missing Permissions"
FORBIDDEN = hikari.ForbiddenError(
    url="https://example.com", headers={}, raw_body=b"", message="test"
)
NOT_FOUND = hikari.NotFoundError(
    url="https://example.com", headers={}, raw_body=b"", message="test"
)

MISSING_THREAD_PERMS_DESCRIPTION = (
    "I am unable to create threads in your suggestions channel, please contact "
    "an administrator and ask them to give me 'Create Public Threads' "
    "permissions.\n\nAlternatively, ask your administrator to disable automatic "
    "thread creation using `/configure`.\n\n"
    "Note your suggestion was still created successfully."
)


def suggestion_sent(sid: str) -> str:
    """The response a user gets once their suggestion is live."""
    return (
        f"Hey, {DISPLAY_NAME}. Your suggestion has been sent to "
        f"<#{CHANNEL_ID}> to be voted on!\n\n"
        "Please wait until it gets approved or rejected by a staff member.\n\n"
        f"Your suggestion ID (sID) for reference is **{sid}**."
    )


def create_bot() -> AsyncMock:
    """Builds a bot whose suggestions channel accepts everything."""
    message = AsyncMock(spec=hikari.Message)
    message.id = MESSAGE_ID
    message.channel_id = CHANNEL_ID

    channel = AsyncMock(spec=hikari.GuildTextChannel)
    channel.mention = f"<#{CHANNEL_ID}>"
    channel.send.return_value = message

    thread = AsyncMock(spec=hikari.GuildThreadChannel)
    thread.id = THREAD_ID

    bot = AsyncMock(spec=hikari.GatewayBot)
    # `rest` is a property, so its children aren't async by default
    bot.rest = AsyncMock(spec=hikari.api.RESTClient)
    bot.rest.fetch_channel.return_value = channel
    bot.rest.create_message_thread.return_value = thread
    return bot


def create_context(bot: AsyncMock) -> AsyncMock:
    """Builds a mocked menu context for the suggesting user."""
    ctx = AsyncMock(spec=lightbulb.components.MenuContext)
    ctx.interaction.locale = "en-GB"
    ctx.user.id = USER_ID
    ctx.guild_id = GUILD_ID
    ctx.client.app = bot
    return ctx


async def suppress_message_addon(user_id: int = USER_ID) -> None:
    """Marks the user as recently shown an addon so responses stay exact."""
    user_config = await configs.ensure_user_config(user_id)
    await MessageAddons(
        shown_message=PossibleMessageAddons.READ_CHANGELOG,
        user=user_config,
    ).save()


async def invoke_suggestion(
    localisations: Localisation,
    *,
    suggestion: str = "test",
    image_urls: list[str] | None = None,
    author_display_name: str = DISPLAY_NAME,
    guild_config: GuildConfigs | None = None,
    bot: AsyncMock | None = None,
    send_final_response: bool = True,
    thread_name: str | None = None,
) -> tuple[AsyncMock, Suggestions | None, AsyncMock, GuildConfigs, UserConfigs]:
    """Creates a suggestion as the given user."""
    if guild_config is None:
        guild_config = await configs.ensure_guild_config(GUILD_ID)
        guild_config.suggestions_channel_id = CHANNEL_ID

    user_config = await configs.ensure_user_config(USER_ID)
    await suppress_message_addon()
    await guild_config.save()

    bot = bot if bot is not None else create_bot()
    ctx = create_context(bot)
    result = await SuggestionMenu.handle_suggestion(
        suggestion=suggestion,
        image_urls=image_urls if image_urls is not None else [],
        author_display_name=author_display_name,
        ctx=cast("lightbulb.components.MenuContext", ctx),
        guild_config=guild_config,
        user_config=user_config,
        localisations=localisations,
        send_final_response=send_final_response,
        thread_name=thread_name,
    )
    return ctx, result, bot, guild_config, user_config


def responded_content(ctx: AsyncMock) -> str:
    """Returns the content the single ephemeral response was sent with."""
    ctx.respond.assert_called_once()
    args, kwargs = ctx.respond.call_args
    assert kwargs["ephemeral"] is True, "Expected suggestion responses to be ephemeral"
    return args[0]


def responded_embed(ctx: AsyncMock) -> hikari.Embed:
    """Returns the embed the single response was sent with."""
    ctx.respond.assert_called_once()
    _, kwargs = ctx.respond.call_args
    return kwargs["embed"]


@pytest.fixture(autouse=True)
def patch_avatar(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Building components otherwise fetches the author's avatar over http."""
    fetch_avatar = AsyncMock(return_value=None)
    monkeypatch.setattr("bot.utils.fetch_user_avatar", fetch_avatar)
    return fetch_avatar


@pytest.fixture(autouse=True)
def patch_autocomplete(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Caching sIDs needs a redis with search, which the fake doesn't have."""
    cache_sid = AsyncMock()
    monkeypatch.setattr(autocomplete, "cache_sid_in_autocomplete", cache_sid)
    return cache_sid


async def test_creates_a_suggestion(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts a suggestion is stored and sent to the suggestions channel."""
    ctx, result, bot, _, user_config = await invoke_suggestion(localisation)

    assert result is not None
    ctx.respond.assert_called_once()
    stored = await Suggestions.objects(Suggestions.user_configuration).first()
    assert stored is not None
    assert stored.sID == result.sID
    assert stored.suggestion == "test"
    assert stored.author_display_name == DISPLAY_NAME
    assert stored.channel_id == CHANNEL_ID
    assert stored.message_id == MESSAGE_ID
    assert stored.user_configuration.user_id == user_config.user_id

    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    _, kwargs = channel.send.call_args
    assert kwargs["role_mentions"] is True
    assert kwargs["components"], "Expected the suggestion to be sent as components"
    assert responded_content(ctx) == suggestion_sent(result.sID)


async def test_no_final_response_when_asked(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts queued suggestions can suppress the confirmation message."""
    ctx, result, _, _, _ = await invoke_suggestion(
        localisation, send_final_response=False
    )

    assert result is not None
    ctx.respond.assert_not_called()


async def test_notifies_users_of_the_new_suggestion(
    localisation: Localisation,
    patch_saq: AsyncMock,
) -> None:
    """Asserts watchers get queued a notification about the suggestion."""
    _, result, _, _, _ = await invoke_suggestion(localisation)

    assert result is not None
    patch_saq.assert_called_once()
    args, kwargs = patch_saq.call_args
    assert args[0] == "notify_users_of_new_suggestion"
    assert kwargs["suggestion_id"] == result.sID
    assert kwargs["guild_id"] == GUILD_ID


async def test_caches_the_sid_for_autocomplete(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    patch_autocomplete: AsyncMock,
) -> None:
    """Asserts new sIDs are made available to autocomplete."""
    _, result, _, _, _ = await invoke_suggestion(localisation)

    assert result is not None
    assert [call.kwargs["index"] for call in patch_autocomplete.call_args_list] == [
        "shared_sid_autocomplete_index",
        "suggestion_sid_autocomplete_index",
    ]
    for call in patch_autocomplete.call_args_list:
        assert call.kwargs["guild_id"] == GUILD_ID
        assert call.kwargs["suggestion_id"] == result.sID


@freeze_time("2025-01-20")
async def test_missing_suggestions_channel_config(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts a guild without a suggestions channel is told to configure one."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.suggestions_channel_id = None
    ctx, result, _, _, _ = await invoke_suggestion(localisation, guild_config=gc)

    assert responded_embed(ctx) == utils.error_embed(
        CHANNEL_NOT_FOUND_TITLE,
        CHANNEL_NOT_FOUND_DESCRIPTION,
        error_code=ErrorCode.MISSING_FETCH_PERMISSIONS_IN_SUGGESTIONS_CHANNEL,
    )
    assert result is None
    assert await Suggestions.count() == 0, (
        "Expected the half created suggestion to be cleaned up"
    )


@freeze_time("2025-01-20")
@pytest.mark.parametrize(
    "error",
    [
        FORBIDDEN,
        NOT_FOUND,
    ],
)
async def test_unreachable_suggestions_channel(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    error: hikari.HikariError,
) -> None:
    """Asserts a channel the bot cannot fetch is reported to the user."""
    bot = create_bot()
    bot.rest.fetch_channel.side_effect = error
    ctx, result, _, _, _ = await invoke_suggestion(localisation, bot=bot)

    assert responded_embed(ctx) == utils.error_embed(
        CHANNEL_NOT_FOUND_TITLE,
        CHANNEL_NOT_FOUND_DESCRIPTION,
        error_code=ErrorCode.MISSING_FETCH_PERMISSIONS_IN_SUGGESTIONS_CHANNEL,
    )
    assert result is None
    assert await Suggestions.count() == 0


@freeze_time("2025-01-20")
async def test_cannot_send_to_suggestions_channel(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts a failed send is recorded as an internal error and reported."""
    bot = create_bot()
    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    channel.send.side_effect = FORBIDDEN
    ctx, result, _, _, _ = await invoke_suggestion(localisation, bot=bot)

    internal_error = await InternalErrors.objects().first()
    assert internal_error is not None
    assert internal_error.guild_id == GUILD_ID
    assert responded_embed(ctx) == utils.error_embed(
        title=MISSING_SEND_PERMS_TITLE,
        description=MISSING_SEND_PERMS_DESCRIPTION,
        internal_error_reference=internal_error,
    )
    assert result is None
    assert await Suggestions.count() == 0


async def test_creates_a_thread(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts a thread is made for the suggestion when the guild wants one."""
    _, result, bot, _, _ = await invoke_suggestion(localisation, thread_name="my thread")

    assert result is not None
    assert result.thread_id == THREAD_ID
    args, _ = bot.rest.create_message_thread.call_args
    assert args[2] == "my thread"

    stored = await Suggestions.objects().first()
    assert stored is not None
    assert stored.thread_id == THREAD_ID


async def test_default_thread_name(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts threads fall back to a name carrying the suggestion id."""
    _, result, bot, _, _ = await invoke_suggestion(localisation)

    assert result is not None
    args, _ = bot.rest.create_message_thread.call_args
    assert args[2] == f"Thread for suggestion {result.sID}"


async def test_thread_name_has_the_sid_injected(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts $SID in a user supplied thread name is filled in."""
    _, result, bot, _, _ = await invoke_suggestion(
        localisation, thread_name="chat about $SID"
    )

    assert result is not None
    args, _ = bot.rest.create_message_thread.call_args
    assert args[2] == f"chat about {result.sID}"


@freeze_time("2025-01-20")
async def test_thread_name_too_long(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts an over long thread name stops the suggestion being made."""
    ctx, result, bot, _, _ = await invoke_suggestion(localisation, thread_name="a" * 100)

    internal_error = await InternalErrors.objects().first()
    assert internal_error is not None
    assert internal_error.error_name == "User Error"
    _, kwargs = ctx.respond.call_args
    assert kwargs["embed"] == utils.error_embed(
        title=THREAD_NAME_TOO_LONG_TITLE,
        description=THREAD_NAME_TOO_LONG_DESCRIPTION,
        internal_error_reference=internal_error,
    )
    assert kwargs["ephemeral"] is True
    assert kwargs["attachment"].filename == "content.txt"
    assert result is None
    assert await Suggestions.count() == 0
    bot.rest.fetch_channel.assert_not_called()


@freeze_time("2025-01-20")
@pytest.mark.parametrize(
    "error",
    [
        FORBIDDEN,
        NOT_FOUND,
    ],
)
async def test_cannot_create_thread(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    error: hikari.HikariError,
) -> None:
    """Asserts a thread the bot cannot create is reported to the user."""
    bot = create_bot()
    bot.rest.create_message_thread.side_effect = error
    ctx, result, _, _, _ = await invoke_suggestion(localisation, bot=bot)

    assert responded_embed(ctx) == utils.error_embed(
        MISSING_THREAD_PERMS_TITLE,
        MISSING_THREAD_PERMS_DESCRIPTION,
        error_code=ErrorCode.MISSING_THREAD_CREATE_PERMISSIONS,
    )
    assert result is None
    assert await Suggestions.count() == 0


async def test_pings_the_author_in_the_thread(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts the author is pinged in their new thread."""
    _, result, bot, _, _ = await invoke_suggestion(localisation)

    assert result is not None
    thread = await bot.rest.create_message_thread()
    thread.send.assert_called_once_with(
        f"Hey {DISPLAY_NAME}, I have created this thread for you to "
        "discuss your suggestion in.",
        user_mentions=True,
    )


async def test_anonymous_authors_are_not_pinged(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts an anonymous author isn't outed by the thread ping."""
    _, result, bot, _, _ = await invoke_suggestion(
        localisation, author_display_name="Anonymous"
    )

    assert result is not None
    thread = await bot.rest.create_message_thread()
    thread.send.assert_not_called()


@pytest.mark.parametrize(
    ("guild_wants_ping", "user_wants_ping"),
    [(False, True), (True, False)],
)
async def test_ping_can_be_turned_off(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    guild_wants_ping: bool,
    user_wants_ping: bool,
) -> None:
    """Asserts either side opting out of the thread ping is honoured."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.suggestions_channel_id = CHANNEL_ID
    gc.ping_on_thread_creation = guild_wants_ping
    user_config = await configs.ensure_user_config(USER_ID)
    user_config.ping_on_thread_creation = user_wants_ping
    await user_config.save()

    _, result, bot, _, _ = await invoke_suggestion(localisation, guild_config=gc)

    assert result is not None
    thread = await bot.rest.create_message_thread()
    thread.send.assert_not_called()


async def test_no_thread_when_disabled(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts guilds which don't want threads don't get one."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.suggestions_channel_id = CHANNEL_ID
    gc.threads_for_suggestions = False
    _, result, bot, _, _ = await invoke_suggestion(localisation, guild_config=gc)

    assert result is not None
    assert result.thread_id is None
    bot.rest.create_message_thread.assert_not_called()
