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
from bot.tables import GuildConfig, InternalError
from tests.conftest import prepare_command


async def invoke_suggest(
    options: Sequence[hikari.CommandInteractionOption],
    user_id: int = None,
    *,
    guild_config: GuildConfig = None,
) -> (lightbulb.Context, GuildConfig):
    if guild_config is None:
        guild_config = mock.Mock(spec=GuildConfig)

    cmd, ctx = await prepare_command(Suggest, options)
    if user_id is not None:
        ctx.user.id = user_id

    await cmd.invoke(ctx, guild_config)
    ctx.defer.assert_called_once_with(ephemeral=True)
    return ctx, guild_config


@freeze_time("2025-01-20")
async def test_suggestion_too_long():
    """Asserts an error message is sent when a suggestion is too long."""
    content = "a" * MAX_CONTENT_LENGTH + "a"
    options: Sequence[hikari.CommandInteractionOption] = [
        hikari.CommandInteractionOption(
            name="suggestion",
            type=hikari.OptionType.STRING,
            value=content,
            options=None,
        ),
    ]
    ctx, guild_config = await invoke_suggest(options)
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
