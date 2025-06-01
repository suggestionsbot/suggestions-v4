import io
from functools import partial
from typing import Sequence
from unittest.mock import patch, MagicMock, AsyncMock

import hikari
import lightbulb
import pytest
from freezegun import freeze_time

from bot import utils
from bot.constants import MAX_CONTENT_LENGTH, ErrorCode
from bot.extensions.suggest import Suggest
from bot.localisation import Localisation
from bot.tables import (
    GuildConfigs,
    InternalErrors,
    Suggestions,
    UserConfigs,
    QueuedSuggestions,
)
from tests.conftest import prepare_command

USER_ID = 12345
GUILD_ID = 23456


def create_options(
    suggestion: str, anon: bool = False, image: bool = False
) -> Sequence[hikari.CommandInteractionOption]:
    options: list[hikari.CommandInteractionOption] = [
        hikari.CommandInteractionOption(
            name="suggestion",
            type=hikari.OptionType.STRING,
            value=suggestion,
            options=None,
        ),
    ]
    if anon:
        options.append(
            hikari.CommandInteractionOption(
                name="anonymously",
                type=hikari.OptionType.BOOLEAN,
                value=anon,
                options=None,
            )
        )

    if image:
        # We need to do pass through and in ctx it gets looked up later
        options.append(
            hikari.CommandInteractionOption(
                name="image",
                type=hikari.OptionType.ATTACHMENT,
                value=hikari.Snowflake(12121),
                options=None,
            )
        )

    return options


async def invoke_suggest(
    options: Sequence[hikari.CommandInteractionOption],
    localisations: Localisation,
    user_id: int = USER_ID,
    guild_id: int = GUILD_ID,
    *,
    image: hikari.files.Bytes = None,
    guild_config: GuildConfigs = None,
    user_config: UserConfigs = None,
    bot: hikari.GatewayBot = None,
) -> (lightbulb.Context, GuildConfigs, UserConfigs, Localisation, hikari.GatewayBot):
    if guild_config is None:
        guild_config = GuildConfigs(id=guild_id)

    if user_config is None:
        user_config = UserConfigs(id=user_id)

    await user_config.save()
    await guild_config.save()

    cmd, ctx = await prepare_command(Suggest, localisations, options)
    ctx.user.id = user_id
    ctx.guild_id = guild_id

    if bot is None:
        bot = AsyncMock(spec=hikari.GatewayBot)

    if image is not None:
        cmd.image = image
        ctx.interaction.resolved.attachments[hikari.Snowflake(12121)] = image

    await cmd.invoke(ctx, guild_config, user_config, localisations, bot)
    ctx.defer.assert_called_once_with(ephemeral=True)
    return ctx, guild_config, user_config, localisations, bot


@freeze_time("2025-01-20")
async def test_suggestion_too_long(localisation):
    """Asserts an error message is sent when a suggestion is too long."""
    content = "a" * MAX_CONTENT_LENGTH + "a"
    options = create_options(content)
    ctx, _, _, _, _ = await invoke_suggest(options, localisations=localisation)
    internal_error = await InternalErrors.objects().first()
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            "Command Failed",
            f"Your content was too long, please limit it to {MAX_CONTENT_LENGTH} characters or less.\n\n"
            "I have attached a file containing your content to save rewriting it entirely.",
            error_code=ErrorCode.SUGGESTION_CONTENT_TOO_LONG,
            internal_error_reference=internal_error,
        ),
        attachment=hikari.files.Bytes(io.StringIO(content), "content.txt"),
    )


@pytest.mark.xfail(reason="Suggestions are not fully implemented yet")
async def test_newline_handling(localisation):
    """Asserts newlines passed in as content end up rendered correctly."""
    options = create_options("a\\nb")
    await invoke_suggest(options, localisations=localisation)
    suggestion: Suggestions = await Suggestions.objects().first()
    assert suggestion.suggestion == "a\nb"


async def test_anonymous_when_disabled(localisation):
    """Asserts that when anon suggestions are disabled that they cant be used"""
    options = create_options("test", anon=True)
    ctx, _, _, _, _ = await invoke_suggest(options, localisations=localisation)
    ctx.respond.assert_called_once_with(
        "Your guild does not allow anonymous suggestions."
    )


async def test_images_when_disabled(localisation):
    """Asserts that when images are disabled that they cant be used"""
    options = create_options("test", image=True)
    gc = GuildConfigs()
    gc.can_have_images_in_suggestions = False
    ctx, _, _, _, _ = await invoke_suggest(
        options,
        localisations=localisation,
        guild_config=gc,
        image=hikari.files.Bytes(io.StringIO("test"), "content.txt"),
    )
    ctx.respond.assert_called_once_with(
        "Your guild does not allow images in suggestions."
    )


@pytest.mark.xfail(reason="Suggestions are not fully implemented yet")
async def test_anonymous_suggestion(localisation):
    """Asserts that created anonymous suggestions are actually anonymous"""
    options = create_options("test", anon=True)
    gc = GuildConfigs()
    gc.can_have_anonymous_suggestions = True
    ctx, _, _, _, _ = await invoke_suggest(
        options,
        localisations=localisation,
        user_id=1,
        guild_config=gc,
    )
    suggestion: Suggestions = await Suggestions.objects(
        Suggestions.user_configuration
    ).first()
    assert suggestion.author_id == 1
    assert suggestion.author_display_name == "Anonymous"


@pytest.mark.xfail(reason="Suggestions are not fully implemented yet")
async def test_image_in_suggestion(localisation):
    """Asserts that suggestions with an image end up uploaded"""

    with patch(
        "bot.utils.upload_file_to_r2",
        new_callable=partial(
            AsyncMock, return_value="https://example.com/fake_image_url"
        ),
    ) as mock:
        options = create_options("test", image=True)
        ctx, _, _, _, _ = await invoke_suggest(
            options,
            localisations=localisation,
            image=hikari.files.Bytes(io.StringIO("test"), "content.txt"),
        )
        suggestion: Suggestions = await Suggestions.objects().first()
        assert suggestion.image_url == "https://example.com/fake_image_url"
        mock.assert_called_once_with(
            file_name="content.txt",
            file_data=bytearray(b"test"),
            guild_id=ctx.guild_id,
            user_id=ctx.user.id,
        )


@freeze_time("2025-01-20")
async def test_queued_suggestion_missing_queue_channel_config(localisation):
    options = create_options("test")
    gc = GuildConfigs()
    gc.uses_suggestions_queue = True
    gc.virtual_suggestions_queue = False
    ctx, _, _, _, _ = await invoke_suggest(
        options, localisations=localisation, guild_config=gc
    )
    internal_error = await InternalErrors.objects().first()
    ctx.respond.assert_called_once()
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            "Command Failed",
            "This command requires a queue channel to use.\n"
            "Please contact an administrator and ask them to set one up "
            "using the following command.\n`/config queue_channel`",
            error_code=ErrorCode.MISSING_QUEUE_CHANNEL,
            internal_error_reference=internal_error,
        ),
    )


@freeze_time("2025-01-20")
async def test_queued_suggestion_missing_queue_channel(localisation):
    """Asserts the bot behaves when it can't fetch the queue channel"""
    options = create_options("test")
    gc = GuildConfigs()
    gc.uses_suggestions_queue = True
    gc.virtual_suggestions_queue = False
    gc.queued_suggestion_channel_id = 12345
    bot = AsyncMock(spec=hikari.GatewayBot)
    bot.rest.fetch_channel.side_effect = hikari.ForbiddenError("test", {}, "test")

    ctx, _, uc, _, _ = await invoke_suggest(
        options,
        localisations=localisation,
        guild_config=gc,
        bot=bot,
    )
    ctx.respond.assert_called_once()
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            "Command Failed",
            "The bot does not have permissions to interact with the queue channel.\nPlease contact an administrator and ask them to ensure the channel exists and that the bot can see it.",
            error_code=ErrorCode.MISSING_PERMISSIONS_IN_QUEUE_CHANNEL,
        ),
    )
    bot.rest.fetch_channel.side_effect = hikari.NotFoundError("test", {}, "test")

    ctx, _, _, _, _ = await invoke_suggest(
        options,
        localisations=localisation,
        guild_config=gc,
        bot=bot,
        user_config=uc,
    )
    ctx.respond.assert_called_once()
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            "Command Failed",
            "The bot does not have permissions to interact with the queue channel.\nPlease contact an administrator and ask them to ensure the channel exists and that the bot can see it.",
            error_code=ErrorCode.MISSING_PERMISSIONS_IN_QUEUE_CHANNEL,
        ),
    )


async def test_channel_queued_suggestions(localisation):
    r_1 = await QueuedSuggestions.count()
    assert r_1 == 0

    options = create_options("test")
    gc = GuildConfigs()
    gc.uses_suggestions_queue = True
    gc.virtual_suggestions_queue = False
    gc.queued_suggestion_channel_id = 12345
    bot = AsyncMock(spec=hikari.GatewayBot)
    bot.rest.fetch_user = AsyncMock()
    bot.rest.fetch_channel = AsyncMock()
    ctx, _, _, _, _ = await invoke_suggest(
        options, localisations=localisation, guild_config=gc, bot=bot
    )

    r_2 = await QueuedSuggestions.count()
    assert r_2 == 1
    r_3: QueuedSuggestions = await QueuedSuggestions.objects(
        QueuedSuggestions.user_configuration
    ).first()
    assert r_3.suggestion == "test"
    assert r_3.author_id == USER_ID
    assert r_3.author_display_name == f"<@{USER_ID}>"


async def test_channel_anonymous_queued_suggestions(localisation):
    r_1 = await QueuedSuggestions.count()
    assert r_1 == 0

    options = create_options("test", anon=True)
    gc = GuildConfigs()
    gc.uses_suggestions_queue = True
    gc.virtual_suggestions_queue = False
    gc.queued_suggestion_channel_id = 12345
    gc.can_have_anonymous_suggestions = True
    bot = AsyncMock(spec=hikari.GatewayBot)
    bot.rest.fetch_user = AsyncMock()
    bot.rest.fetch_channel = AsyncMock()
    ctx, _, _, _, _ = await invoke_suggest(
        options, localisations=localisation, guild_config=gc, bot=bot
    )

    r_2 = await QueuedSuggestions.count()
    assert r_2 == 1
    r_3: QueuedSuggestions = await QueuedSuggestions.objects(
        QueuedSuggestions.user_configuration
    ).first()
    assert r_3.suggestion == "test"
    assert r_3.author_id == USER_ID
    assert r_3.author_display_name == "Anonymous"
