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
                        localisations.get_localized_string(
                            "values.suggest.content_too_long_title",
                            ctx=ctx,
                        ),
                        localisations.get_localized_string(
                            "values.suggest.content_too_long_description",
                            ctx=ctx,
                            extras={"MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH},
                        ),
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

        if (
            self.anonymously is True
            and guild_config.can_have_anonymous_suggestions is False
        ):
            await ctx.respond(
                localisations.get_localized_string(
                    "values.suggest.no_anonymous_suggestions", ctx
                )
            )
            return None

        image_url: str | None = None
        if self.image is not None:
            if guild_config.can_have_images_in_suggestions is False:
                await ctx.respond(
                    localisations.get_localized_string(
                        "values.suggest.no_images_in_suggestions", ctx
                    )
                )
                return None

            image_url = await utils.upload_file_to_r2(
                file_name=self.image.filename,
                file_data=await self.image.read(),
                guild_id=ctx.guild_id,
                user_id=ctx.user.id,
            )

        # TODO Implement more
        raise ValueError("Who knows")
