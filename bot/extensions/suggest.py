import io

import hikari
import lightbulb

from bot import utils
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MessageTooLong
from bot.localisation import Localisation
from bot.tables import GuildConfig, InternalError, UserConfig

loader = lightbulb.Loader()


def handle_suggestions_errors(func):
    func = lightbulb.di.with_di(func)

    async def _wrapper(
        command_data,
        ctx: lightbulb.Context,
        guild_config: GuildConfig,
        user_config: UserConfig,
        localisations: Localisation,
    ):
        try:
            return await func(
                command_data,
                ctx=ctx,
                guild_config=guild_config,
                user_config=user_config,
                localisations=localisations,
            )
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
    name="commands.suggest.name",
    description="commands.suggest.description",
    localize=True,
):
    suggestion = lightbulb.string(
        "commands.suggest.options.suggestion.name",
        "commands.suggest.options.suggestion.description",
        localize=True,
    )
    image = lightbulb.attachment(
        "commands.suggest.options.image.name",
        "commands.suggest.options.image.description",
        default=None,
        localize=True,
    )
    anonymously = lightbulb.boolean(
        "commands.suggest.options.anonymously.name",
        "commands.suggest.options.anonymously.description",
        default=False,
        localize=True,
    )

    @lightbulb.invoke
    @handle_suggestions_errors
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfig,
        user_config: UserConfig,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if len(self.suggestion) > MAX_CONTENT_LENGTH:
            raise MessageTooLong(self.suggestion)

        # TODO Implement more
        raise ValueError("Who knows")
