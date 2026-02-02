import asyncio
import io
import logging
import uuid
from datetime import timedelta
from typing import cast

import hikari
import lightbulb
import orjson
from fastnanoid import generate
from hikari.impl import MessageActionRowBuilder, special_endpoints
from lightbulb.components import base
from opentelemetry import trace

import shared
import web.constants
from bot import utils, constants, menus
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MessageTooLong, MissingQueueChannel
from bot.localisation import Localisation
from bot.tables import InternalErrors
from shared.tables import GuildConfigs, UserConfigs, QueuedSuggestions

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


def handle_suggestions_errors(func):
    func = lightbulb.di.with_di(func)

    async def _wrapper(
        command_data,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ):
        try:
            return await func(
                command_data,
                ctx=ctx,
                bot=bot,
                guild_config=guild_config,
                user_config=user_config,
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
                                    ctx=ctx,
                                ),
                                localisations.get_localized_string(
                                    "errors.suggest.content_too_long.description",
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

                    elif isinstance(exception, MissingQueueChannel):
                        await ctx.respond(
                            embed=utils.error_embed(
                                localisations.get_localized_string(
                                    "errors.suggest.missing_queue_channel.title",
                                    ctx=ctx,
                                ),
                                localisations.get_localized_string(
                                    "errors.suggest.missing_queue_channel.description",
                                    ctx=ctx,
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
        client: lightbulb.Client,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ) -> None:
        components = await menus.SuggestionMenu.build_suggest_modal(
            guild_config=guild_config, localisations=localisations, ctx=ctx
        )

        link_id: str = await utils.otel.generate_trace_link_state()
        await ctx.interaction.create_modal_response(
            "Create Suggestion",
            f"suggest_modal:{link_id}",
            components=components,
        )
