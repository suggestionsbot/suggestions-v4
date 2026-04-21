import io
import logging

import hikari
import lightbulb

from bot import utils, menus
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MessageTooLong, MissingQueueChannel
from bot.localisation import Localisation
from bot.tables import InternalErrors
from shared.tables import GuildConfigs

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


def handle_suggestions_errors(func):
    func = lightbulb.di.with_di(func)

    async def _wrapper(
        command_data,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ):
        try:
            return await func(
                command_data,
                ctx=ctx,
                guild_config=guild_config,
                localisations=localisations,
            )
        except Exception as exception:
            this_will_handle: tuple[type[Exception], ...] = (
                MessageTooLong,
                MissingQueueChannel,
            )
            if isinstance(exception, this_will_handle):
                with utils.start_error_span(exception, "command error handler"):
                    internal_error: InternalErrors = await InternalErrors.persist_error(
                        exception,
                        command_name="suggest",
                        guild_id=ctx.guild_id,
                        user_id=ctx.user.id,
                    )

                    if isinstance(exception, MessageTooLong):
                        await ctx.respond(
                            embed=utils.error_embed(
                                localisations.get_localized_string(
                                    "errors.suggest.content_too_long.title",
                                    ctx.interaction.locale,
                                ),
                                localisations.get_localized_string(
                                    "errors.suggest.content_too_long.description",
                                    ctx.interaction.locale,
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

                    elif isinstance(exception, MissingQueueChannel):
                        await ctx.respond(
                            embed=utils.error_embed(
                                localisations.get_localized_string(
                                    "errors.suggest.missing_queue_channel.title",
                                    ctx.interaction.locale,
                                ),
                                localisations.get_localized_string(
                                    "errors.suggest.missing_queue_channel.description",
                                    ctx.interaction.locale,
                                ),
                                error_code=ErrorCode.MISSING_QUEUE_CHANNEL,
                                internal_error_reference=internal_error,
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
    contexts=[hikari.ApplicationContextType.GUILD],
):

    @lightbulb.invoke
    @handle_suggestions_errors
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> None:
        if ctx.user.id in guild_config.blocked_users:
            await ctx.respond(
                embed=utils.error_embed(
                    localisations.get_localized_string(
                        "commands.suggest.responses.blocked.title", ctx.interaction.locale
                    ),
                    localisations.get_localized_string(
                        "commands.suggest.responses.blocked.description",
                        ctx.interaction.locale,
                    ),
                ),
                ephemeral=True,
            )
            return None

        components = await menus.SuggestionMenu.build_suggest_modal(
            guild_config=guild_config, localisations=localisations, ctx=ctx
        )

        link_id: str = await utils.otel.generate_trace_link_state()
        await ctx.interaction.create_modal_response(
            localisations.get_localized_string(
                "commands.suggest.responses.menu_title", ctx.interaction.locale
            ),
            f"suggest_modal:{link_id}",
            components=components,
        )
        return None
