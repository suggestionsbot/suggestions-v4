import datetime
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
from shared.tables import GuildConfigs, QueuedSuggestions, UserConfigs
from shared.utils import autocomplete, configs
from web.tables import GuildTokens
from web.util.table_mixins import utc_now

USER_ID = 12345
GUILD_ID = 23456
CHANNEL_ID = 348934
MESSAGE_ID = 555666
DISPLAY_NAME = f"Skelmis (<@{USER_ID}>)"

SENT_TO_QUEUE = "Your suggestion has been sent to the queue for processing."
CHANGELOG_ADDON = (
    "On top of this, we would also just like to inform you that we have "
    "recently released a new version of the bot. We'd recommend reading our "
    "changelog at <https://docs.suggestions.gg/> to learn about what has "
    "changed. Thank you!"
)
MISSING_QUEUE_CHANNEL_TITLE = "Command Failed"
MISSING_QUEUE_CHANNEL_DESCRIPTION = (
    "This command requires a queue channel to use.\n"
    "Please contact an administrator and ask them to set one up "
    "using the following command.\n`/configure guild`"
)
QUEUE_CHANNEL_NOT_FOUND_TITLE = "Command Failed"
QUEUE_CHANNEL_NOT_FOUND_DESCRIPTION = (
    "The bot does not have permissions to interact with the queue channel.\n"
    "Please contact an administrator and ask them to ensure the channel exists "
    "and that the bot can see it."
)
MISSING_SEND_PERMS_TITLE = "Command Failed"
MISSING_SEND_PERMS_DESCRIPTION = (
    "The bot does not have permissions to interact with the suggestions queue "
    "channel.\nPlease contact an administrator and ask them to ensure the "
    "channel exists and that the bot can see it/send messages to it."
)
FORBIDDEN = hikari.ForbiddenError(
    url="https://example.com", headers={}, raw_body=b"", message="test"
)
NOT_FOUND = hikari.NotFoundError(
    url="https://example.com", headers={}, raw_body=b"", message="test"
)


def create_bot() -> AsyncMock:
    """Builds a bot whose queue channel accepts everything."""
    message = AsyncMock(spec=hikari.Message)
    message.id = MESSAGE_ID
    message.channel_id = CHANNEL_ID

    channel = AsyncMock(spec=hikari.GuildTextChannel)
    channel.mention = f"<#{CHANNEL_ID}>"
    channel.send.return_value = message

    bot = AsyncMock(spec=hikari.GatewayBot)
    # `rest` is a property, so its children aren't async by default
    bot.rest = AsyncMock(spec=hikari.api.RESTClient)
    bot.rest.fetch_channel.return_value = channel
    return bot


def create_context(bot: AsyncMock) -> AsyncMock:
    """Builds a mocked menu context for the suggesting user."""
    ctx = AsyncMock(spec=lightbulb.components.MenuContext)
    ctx.interaction.locale = "en-GB"
    ctx.user.id = USER_ID
    ctx.user.display_name = "Skelmis"
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


async def invoke_queued_suggestion(
    localisations: Localisation,
    *,
    suggestion: str = "test",
    image_urls: list[str] | None = None,
    is_anonymous: bool = False,
    guild_config: GuildConfigs | None = None,
    bot: AsyncMock | None = None,
    suppress_addon: bool = True,
) -> tuple[AsyncMock, AsyncMock, GuildConfigs, UserConfigs]:
    """Queues a suggestion as the given user."""
    if guild_config is None:
        guild_config = await configs.ensure_guild_config(GUILD_ID)

    user_config = await configs.ensure_user_config(USER_ID)
    if suppress_addon:
        await suppress_message_addon()
    await guild_config.save()

    bot = bot if bot is not None else create_bot()
    ctx = create_context(bot)
    await SuggestionMenu.handle_queued_suggestion(
        suggestion=suggestion,
        image_urls=image_urls if image_urls is not None else [],
        is_anonymous=is_anonymous,
        ctx=cast("lightbulb.components.MenuContext", ctx),
        guild_config=guild_config,
        user_config=user_config,
        localisations=localisations,
    )
    return ctx, bot, guild_config, user_config


async def grant_premium(*, expired: bool = False) -> None:
    """Gives the guild an active premium token, as redeeming one would."""
    offset = datetime.timedelta(days=-1 if expired else 30)
    await GuildTokens(
        subscription_id="sub_test",
        subscription_item_id="si_test",
        used_for_guild=GUILD_ID,
        expires_at=utc_now() + offset,
    ).save()


async def physical_queue_config() -> GuildConfigs:
    """A guild config which sends queued suggestions to a real channel."""
    guild_config = await configs.ensure_guild_config(GUILD_ID)
    guild_config.virtual_suggestions_queue = False
    guild_config.queued_suggestion_channel_id = CHANNEL_ID
    return guild_config


def responded_content(ctx: AsyncMock) -> str:
    """Returns the content the single ephemeral response was sent with."""
    ctx.respond.assert_called_once()
    args, kwargs = ctx.respond.call_args
    assert kwargs["ephemeral"] is True, "Expected queue responses to be ephemeral"
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


async def test_queues_a_suggestion_virtually(localisation: Localisation) -> None:
    """Asserts a virtual queue stores the suggestion without sending it."""
    ctx, bot, _, user_config = await invoke_queued_suggestion(localisation)

    stored = await QueuedSuggestions.objects(QueuedSuggestions.user_configuration).first()
    assert stored is not None
    assert stored.suggestion == "test"
    assert stored.author_display_name == DISPLAY_NAME
    assert stored.image_urls == []
    assert stored.channel_id is None
    assert stored.message_id is None
    assert stored.is_physical is False
    assert stored.user_configuration.user_id == user_config.user_id

    bot.rest.fetch_channel.assert_not_called()
    assert responded_content(ctx) == SENT_TO_QUEUE


async def test_stores_image_urls(localisation: Localisation) -> None:
    """Asserts uploaded images are kept against the queued suggestion."""
    await invoke_queued_suggestion(
        localisation, image_urls=["https://example.com/one.png"]
    )

    stored = await QueuedSuggestions.objects().first()
    assert stored is not None
    assert stored.image_urls == ["https://example.com/one.png"]


async def test_anonymous_authors_are_not_named(localisation: Localisation) -> None:
    """Asserts an anonymous suggestion doesn't record the author's name."""
    await invoke_queued_suggestion(localisation, is_anonymous=True)

    stored = await QueuedSuggestions.objects().first()
    assert stored is not None
    assert stored.author_display_name == "Anonymous"
    assert stored.is_anonymous is True


async def test_caches_the_sid_for_autocomplete(
    localisation: Localisation,
    patch_autocomplete: AsyncMock,
) -> None:
    """Asserts new sIDs are made available to both autocomplete indexes."""
    await invoke_queued_suggestion(localisation)

    stored = await QueuedSuggestions.objects().first()
    assert stored is not None
    assert [call.kwargs["index"] for call in patch_autocomplete.call_args_list] == [
        "shared_sid_autocomplete_index",
        "queue_sid_autocomplete_index",
    ]
    for call in patch_autocomplete.call_args_list:
        assert call.kwargs["guild_id"] == GUILD_ID
        assert call.kwargs["suggestion_id"] == stored.sID


async def test_appends_the_message_addon(localisation: Localisation) -> None:
    """Asserts a user due an addon gets it alongside the confirmation."""
    ctx, _, _, _ = await invoke_queued_suggestion(localisation, suppress_addon=False)

    assert responded_content(ctx) == f"{SENT_TO_QUEUE}\n\n\n{CHANGELOG_ADDON}"


async def test_sends_to_the_queue_channel(localisation: Localisation) -> None:
    """Asserts a physical queue posts the suggestion to its channel."""
    ctx, bot, _, _ = await invoke_queued_suggestion(
        localisation, guild_config=await physical_queue_config()
    )

    bot.rest.fetch_channel.assert_awaited_once_with(CHANNEL_ID)
    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    _, kwargs = channel.send.call_args
    assert kwargs["role_mentions"] is True
    assert kwargs["components"], "Expected the suggestion to be sent as components"

    stored = await QueuedSuggestions.objects().first()
    assert stored is not None
    assert stored.channel_id == CHANNEL_ID
    assert stored.message_id == MESSAGE_ID
    assert stored.is_physical is True
    assert responded_content(ctx) == SENT_TO_QUEUE


@freeze_time("2025-01-20")
async def test_missing_queue_channel_config(localisation: Localisation) -> None:
    """Asserts a physical queue without a channel is told to configure one."""
    guild_config = await physical_queue_config()
    guild_config.queued_suggestion_channel_id = None
    ctx, bot, _, _ = await invoke_queued_suggestion(
        localisation, guild_config=guild_config
    )

    assert responded_embed(ctx) == utils.error_embed(
        MISSING_QUEUE_CHANNEL_TITLE,
        MISSING_QUEUE_CHANNEL_DESCRIPTION,
        error_code=ErrorCode.MISSING_QUEUE_CHANNEL,
    )
    bot.rest.fetch_channel.assert_not_called()


@freeze_time("2025-01-20")
@pytest.mark.parametrize(
    "error",
    [
        FORBIDDEN,
        NOT_FOUND,
    ],
)
async def test_unreachable_queue_channel(
    localisation: Localisation,
    error: hikari.HikariError,
) -> None:
    """Asserts a channel the bot cannot fetch is reported to the user."""
    bot = create_bot()
    bot.rest.fetch_channel.side_effect = error
    ctx, _, _, _ = await invoke_queued_suggestion(
        localisation, guild_config=await physical_queue_config(), bot=bot
    )

    assert responded_embed(ctx) == utils.error_embed(
        QUEUE_CHANNEL_NOT_FOUND_TITLE,
        QUEUE_CHANNEL_NOT_FOUND_DESCRIPTION,
        error_code=ErrorCode.MISSING_PERMISSIONS_IN_QUEUE_CHANNEL,
    )


@freeze_time("2025-01-20")
async def test_cannot_send_to_queue_channel(localisation: Localisation) -> None:
    """Asserts a failed send is recorded as an internal error and rolled back."""
    bot = create_bot()
    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    channel.send.side_effect = FORBIDDEN
    ctx, _, _, _ = await invoke_queued_suggestion(
        localisation, guild_config=await physical_queue_config(), bot=bot
    )

    internal_error = await InternalErrors.objects().first()
    assert internal_error is not None
    assert internal_error.guild_id == GUILD_ID
    assert responded_embed(ctx) == utils.error_embed(
        title=MISSING_SEND_PERMS_TITLE,
        description=MISSING_SEND_PERMS_DESCRIPTION,
        internal_error_reference=internal_error,
    )
    assert await QueuedSuggestions.count() == 0, (
        "Expected the half created suggestion to be cleaned up"
    )


async def test_premium_guilds_get_their_queue_prefix(
    localisation: Localisation,
) -> None:
    """Asserts a premium prefix is sent above the queued suggestion."""
    await grant_premium()
    guild_config = await physical_queue_config()
    guild_config.premium.queued_suggestions_prefix = "<@&987>"
    await guild_config.premium.save()

    _, bot, _, _ = await invoke_queued_suggestion(localisation, guild_config=guild_config)

    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    _, kwargs = channel.send.call_args
    assert kwargs["components"][0].content == "<@&987>"


@pytest.mark.parametrize(
    ("has_token", "expired"),
    [(False, False), (True, True)],
)
async def test_no_prefix_without_active_premium(
    localisation: Localisation,
    has_token: bool,
    expired: bool,
) -> None:
    """Asserts the prefix is ignored without an unexpired premium token."""
    if has_token:
        await grant_premium(expired=expired)

    guild_config = await physical_queue_config()
    guild_config.premium.queued_suggestions_prefix = "<@&987>"
    await guild_config.premium.save()

    _, bot, _, _ = await invoke_queued_suggestion(localisation, guild_config=guild_config)

    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    _, kwargs = channel.send.call_args
    assert not isinstance(
        kwargs["components"][0], hikari.impl.TextDisplayComponentBuilder
    ), "Expected no prefix for a guild without premium"


async def test_premium_guilds_without_a_prefix_send_nothing_extra(
    localisation: Localisation,
) -> None:
    """Asserts premium alone doesn't add a prefix component."""
    await grant_premium()

    _, bot, _, _ = await invoke_queued_suggestion(
        localisation, guild_config=await physical_queue_config()
    )

    channel = await bot.rest.fetch_channel(CHANNEL_ID)
    _, kwargs = channel.send.call_args
    assert not isinstance(
        kwargs["components"][0], hikari.impl.TextDisplayComponentBuilder
    ), "Expected no prefix when the guild hasn't set one"
