import io

import hikari
import lightbulb

from bot import utils
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MessageTooLong
from bot.tables import GuildConfig, InternalError

loader = lightbulb.Loader()


def error_handled(func):
    func = lightbulb.di.with_di(func)

    async def _wrapper(command_data, ctx: lightbulb.Context, guild_config: GuildConfig):
        try:
            return await func(command_data, ctx, guild_config)
        except Exception as exception:
            internal_error: InternalError = await InternalError.persist_error(
                exception,
                command_name="suggest",
                guild_id=ctx.guild_id,
                author_id=ctx.user.id,
            )

            if isinstance(exception, MessageTooLong):
                await ctx.respond(
                    embed=utils.error_embed(
                        "Command failed",
                        f"Your content was too long, please limit it to {MAX_CONTENT_LENGTH} characters or less.\n\n"
                        "I have attached a file containing your content to save rewriting it entirely.",
                        error_code=ErrorCode.SUGGESTION_CONTENT_TOO_LONG,
                        internal_error_reference=internal_error,
                    ),
                    attachment=hikari.files.Bytes(
                        io.StringIO(exception.message_text), "content.txt"
                    ),
                )
                return None

            raise

    return _wrapper


@loader.command
class Suggest(
    lightbulb.SlashCommand,
    name="suggest",
    description="Create a new suggestion.",
):
    suggestion = lightbulb.string("suggestion", "Your suggestion.")
    image = lightbulb.attachment(
        "image",
        "An image to add to your suggestion.",
        default=None,
    )
    anonymously = lightbulb.boolean(
        "anonymously",
        "Submit your suggestion anonymously.",
        default=False,
    )

    @lightbulb.invoke
    @error_handled
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfig,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if len(self.suggestion) > 1:
            raise MessageTooLong(self.suggestion)

        # TODO Implement more
        raise ValueError("Who knows")
