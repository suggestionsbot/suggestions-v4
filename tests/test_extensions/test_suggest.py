import io
from typing import Sequence
from unittest import mock

import hikari
import lightbulb
from freezegun import freeze_time
from hikari import Bytes

from bot import utils
from bot.constants import MAX_CONTENT_LENGTH, ErrorCode
from bot.extensions.suggest import Suggest
from bot.localisation import Localisation
from bot.tables import GuildConfig, InternalError, Suggestions, UserConfig
from tests.conftest import prepare_command


def create_options(suggestion: str) -> Sequence[hikari.CommandInteractionOption]:
    options: Sequence[hikari.CommandInteractionOption] = [
        hikari.CommandInteractionOption(
            name="suggestion",
            type=hikari.OptionType.STRING,
            value=suggestion,
            options=None,
        ),
    ]
    return options


async def invoke_suggest(
    options: Sequence[hikari.CommandInteractionOption],
    user_id: int = None,
    *,
    guild_config: GuildConfig = None,
    user_config: UserConfig = None,
    localisations: Localisation = None,
) -> (lightbulb.Context, GuildConfig, UserConfig, Localisation):
    if guild_config is None:
        guild_config = mock.Mock(spec=GuildConfig)

    if user_config is None:
        user_config = mock.Mock(spec=UserConfig)

    if localisations is None:
        localisations = mock.Mock(spec=UserConfig)

    cmd, ctx = await prepare_command(Suggest, options)
    if user_id is not None:
        ctx.user.id = user_id

    await cmd.invoke(ctx, guild_config, user_config, localisations)
    ctx.defer.assert_called_once_with(ephemeral=True)
    return ctx, guild_config, user_config, localisations


@freeze_time("2025-01-20")
async def test_suggestion_too_long(localisation):
    """Asserts an error message is sent when a suggestion is too long."""
    content = "a" * MAX_CONTENT_LENGTH + "a"
    options = create_options(content)
    ctx, _, _, _ = await invoke_suggest(options, localisations=localisation)
    internal_error = await InternalError.objects().first()
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            "Command failed",
            f"Your content was too long, please limit it to {MAX_CONTENT_LENGTH} characters or less.\n\n"
            "I have attached a file containing your content to save rewriting it entirely.",
            error_code=ErrorCode.SUGGESTION_CONTENT_TOO_LONG,
            internal_error_reference=internal_error,
        ),
        attachment=hikari.files.Bytes(io.StringIO(content), "content.txt"),
    )


async def test_newline_handling(localisation):
    """Asserts newlines passed in as content end up rendered correctly."""
    options = create_options("a\\nb")
    await invoke_suggest(options, localisations=localisation)
    suggestion: Suggestions = await Suggestions.objects().first()
    assert suggestion.suggestion == "a\nb"
