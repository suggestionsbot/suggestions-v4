import asyncio
import io
import logging
import uuid
from typing import cast

import hikari
import lightbulb
from hikari.impl import MessageActionRowBuilder, special_endpoints
from lightbulb.components import base

import shared
from bot import utils, constants
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
        components = [
            hikari.impl.LabelComponentBuilder(
                label="Suggestion",
                description="Your Suggestion",
                component=hikari.impl.TextInputBuilder(
                    custom_id="suggestion",
                    label="suggestion",
                    style=hikari.TextInputStyle.PARAGRAPH,
                    required=True,
                    min_length=1,
                    max_length=constants.MAX_CONTENT_LENGTH,
                ),
            ),
        ]
        if guild_config.can_have_images_in_suggestions:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label="Images",
                    description="Upload images to show alongside your suggestion",
                    component=hikari.impl.FileUploadComponentBuilder(
                        custom_id="files",
                        min_values=1,
                        max_values=5,
                        is_required=False,
                    ),
                )
            )

        if guild_config.can_have_anonymous_suggestions:
            hikari.impl.LabelComponentBuilder(
                label="Anonymously",
                description='Want to show up in the UI as "Anonymous"? Defaults to No',
                component=hikari.impl.TextSelectMenuBuilder(
                    custom_id="anonymously",
                    parent=None,
                    options=[
                        hikari.impl.SelectOptionBuilder("no", "No"),
                        hikari.impl.SelectOptionBuilder("yes", "Yes"),
                    ],
                    min_values=1,
                    max_values=1,
                    is_required=False,
                ),
            ),

        await ctx.interaction.create_modal_response(
            "Create Suggestion",
            "suggest_modal",
            components=components,
        )
