import io
import logging
from typing import cast

import commons
import hikari
import lightbulb

from bot import constants, utils
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MissingQueueChannel, MessageTooLong
from bot.localisation import Localisation
from bot.tables import InternalErrors
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    QueuedSuggestions,
    Suggestions,
    SuggestionStateEnum,
)
from shared.utils import r2

logger = logging.getLogger(__name__)


class SuggestionMenu:
    @classmethod
    async def handle_interaction(
        cls,
        response_fields: list[
            hikari.interactions.modal_interactions.ModalInteractionTextInputComponent
            | hikari.interactions.modal_interactions.ModalInteractionFileUploadComponent
            | hikari.interactions.modal_interactions.ModalInteractionStringSelectComponent
        ],
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        event: hikari.ModalInteractionCreateEvent,
    ):
        await ctx.defer(ephemeral=True)
        try:
            suggestion_content: str | None = None
            image_urls: list[str] = []
            anonymously: bool = False
            for entry in response_fields:
                if entry.custom_id == "suggestion":
                    entry = cast(
                        hikari.interactions.modal_interactions.ModalInteractionTextInputComponent,
                        entry,
                    )
                    suggestion_content = entry.value

                elif entry.custom_id == "anonymously":
                    entry = cast(
                        hikari.interactions.modal_interactions.ModalInteractionStringSelectComponent,
                        entry,
                    )
                    anonymously = commons.value_to_bool(entry.values[0])

                elif entry.custom_id == "files":
                    if guild_config.can_have_images_in_suggestions is False:
                        await ctx.respond(
                            localisations.get_localized_string(
                                "values.suggest.no_images_in_suggestions", ctx
                            )
                        )
                        return None

                    entry = cast(
                        hikari.interactions.modal_interactions.ModalInteractionFileUploadComponent,
                        entry,
                    )
                    for item_id in entry.values:
                        item: hikari.messages.Attachment | None = (
                            event.interaction.resolved.attachments.get(item_id)
                        )
                        if item is None:
                            logger.critical(
                                f"failed to find an image in the resolved attachments"
                            )
                            continue

                        image_urls.append(
                            await r2.upload_file_to_r2(
                                file_name=item.filename,
                                # TODO try optimise this to do image streaming?
                                file_data=await item.read(),
                                guild_id=guild_config.guild_id,
                                user_id=user_config.user_id,
                            )
                        )

            if len(suggestion_content) > MAX_CONTENT_LENGTH:
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
                    ),
                    attachment=hikari.files.Bytes(
                        io.StringIO(suggestion_content), "content.txt"
                    ),
                )
                return None

            if (
                anonymously is True
                and guild_config.can_have_anonymous_suggestions is False
            ):
                await ctx.respond(
                    localisations.get_localized_string(
                        "values.suggest.no_anonymous_suggestions", ctx
                    )
                )
                return None

            if guild_config.uses_suggestions_queue:
                return await cls.handle_queued_suggestion(
                    suggestion=suggestion_content,
                    image_urls=image_urls,
                    is_anonymous=anonymously,
                    ctx=ctx,
                    guild_config=guild_config,
                    user_config=user_config,
                    localisations=localisations,
                )

            else:
                return await cls.handle_suggestion(
                    suggestion=suggestion_content,
                    image_urls=image_urls,
                    is_anonymous=anonymously,
                    ctx=ctx,
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

    @classmethod
    async def handle_suggestion(
        cls,
        *,
        suggestion: str,
        image_urls: list[str],
        is_anonymous: bool,
        ctx: lightbulb.components.MenuContext,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ):
        """Specific helper for handling queued suggestions"""
        bot = ctx.client.app
        s: Suggestions = Suggestions(
            guild_configuration=guild_config,
            user_configuration=user_config,
            suggestion=suggestion,
            image_urls=image_urls,
            author_display_name=(
                f"<@{ctx.user.id}>" if is_anonymous is False else "Anonymous"
            ),
            state=SuggestionStateEnum.PENDING,
        )
        await s.save()
        try:
            channel = await bot.rest.fetch_channel(guild_config.suggestions_channel_id)
            channel = cast(hikari.GuildTextChannel, channel)
        except (hikari.ForbiddenError, hikari.NotFoundError):
            await ctx.respond(
                embed=utils.error_embed(
                    localisations.get_localized_string(
                        "errors.suggest.suggest_channel_not_found.title",
                        ctx=ctx,
                    ),
                    localisations.get_localized_string(
                        "errors.suggest.suggest_channel_not_found.description",
                        ctx=ctx,
                    ),
                    error_code=ErrorCode.MISSING_FETCH_PERMISSIONS_IN_SUGGESTIONS_CHANNEL,
                ),
            )
            return None

        prefix = (
            guild_config.premium.suggestions_prefix
            if await guild_config.premium_is_enabled(ctx)
            else ""
        )
        message: hikari.Message = await channel.send(
            content=prefix,
            components=await s.as_components(
                bot=bot,
                ctx=ctx,
                localisations=localisations,
                use_guild_locale=True,
                guild_config=guild_config,
            ),
        )
        s.channel_id = message.channel_id
        s.message_id = message.id
        await s.save()

        if guild_config.threads_for_suggestions:
            try:
                thread = await bot.rest.create_message_thread(
                    channel, message, f"Thread for suggestion {s.sID}"
                )
            except (hikari.ForbiddenError, hikari.NotFoundError):
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "errors.suggest.missing_create_thread_perms.title",
                            ctx=ctx,
                        ),
                        localisations.get_localized_string(
                            "errors.suggest.missing_create_thread_perms.description",
                            ctx=ctx,
                        ),
                        error_code=ErrorCode.MISSING_THREAD_CREATE_PERMISSIONS,
                    ),
                )
                return None

            if guild_config.ping_on_thread_creation and not s.is_anonymous:
                try:
                    await thread.send(
                        localisations.get_localized_string(
                            "values.suggest.ping_author_in_thread",
                            ctx,
                            extras={"AUTHOR": s.author_display_name},
                        ),
                        user_mentions=True,
                    )
                except (hikari.ForbiddenError, hikari.NotFoundError):
                    # I'd consider it 'fine' if the bot can't send this message
                    pass

        if not (guild_config.dm_messages_disabled or user_config.dm_messages_disabled):
            try:
                dm_channel = await bot.rest.create_dm_channel(ctx.user)
                await dm_channel.send(
                    localisations.get_localized_string(
                        "dms.suggest.suggestion_created",
                        ctx,
                        extras={
                            "AUTHOR": s.author_display_name,
                            "CHANNEL": channel.mention,
                            "SUGGESTION_LINK": f"https://discord.com/channels/{ctx.guild_id}/{channel.id}/{message.id}",
                        },
                    ),
                )
                await dm_channel.send(
                    components=await s.as_components(
                        bot=bot,
                        ctx=ctx,
                        localisations=localisations,
                        exclude_buttons=True,
                        exclude_votes=True,
                    ),
                )
            except (hikari.ForbiddenError,):
                # I'd consider it 'fine' if the bot can't send this message
                logger.debug(
                    "Failed to dm user about a suggestion",
                    extra={
                        "interaction.user.id": ctx.user.id,
                        "interaction.user.username": ctx.user.display_name,
                        "interaction.guild.id": ctx.guild_id,
                        "suggestion.id": s.sID,
                    },
                )

        await ctx.respond(
            localisations.get_localized_string(
                "values.suggest.suggestion_sent",
                ctx,
                extras={
                    "AUTHOR": s.author_display_name,
                    "CHANNEL": channel.mention,
                    "SID": s.sID,
                },
            ),
            ephemeral=True,
        )
        return None

    @classmethod
    async def handle_queued_suggestion(
        cls,
        *,
        suggestion: str,
        image_urls: list[str],
        is_anonymous: bool,
        ctx: lightbulb.components.MenuContext,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ):
        """Specific helper for handling queued suggestions"""
        bot = ctx.client.app
        qs: QueuedSuggestions = QueuedSuggestions(
            guild_configuration=guild_config,
            user_configuration=user_config,
            suggestion=suggestion,
            image_urls=image_urls,
            author_display_name=(
                f"<@{ctx.user.id}>" if is_anonymous is False else "Anonymous"
            ),
        )

        if guild_config.virtual_suggestions_queue is False:
            # Need to send to a channel
            if guild_config.queued_suggestion_channel_id is None:
                raise MissingQueueChannel

            try:
                channel = await bot.rest.fetch_channel(
                    guild_config.queued_suggestion_channel_id
                )
                channel = cast(hikari.GuildTextChannel, channel)
            except (hikari.ForbiddenError, hikari.NotFoundError):
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "errors.suggest.queue_channel_not_found.title",
                            ctx=ctx,
                        ),
                        localisations.get_localized_string(
                            "errors.suggest.queue_channel_not_found.description",
                            ctx=ctx,
                        ),
                        error_code=ErrorCode.MISSING_PERMISSIONS_IN_QUEUE_CHANNEL,
                    ),
                )
                return None

            prefix = (
                guild_config.premium.queued_suggestions_prefix
                if guild_config.premium_is_enabled(ctx)
                else ""
            )
            message: hikari.Message = await channel.send(
                content=prefix,
                components=await qs.as_components(
                    bot=bot, ctx=ctx, localisations=localisations
                ),
            )
            qs.channel_id = message.channel_id
            qs.message_id = message.id

        await qs.save()
        logger.debug(
            f"User {ctx.user.id} created new queued"
            f" suggestion in guild {ctx.guild_id}",
            extra={
                "interaction.user.id": ctx.user.id,
                "interaction.guild.id": ctx.guild_id,
            },
        )
        await ctx.respond(
            localisations.get_localized_string(
                "values.suggest.sent_to_queue",
                ctx,
                guild_config=guild_config,
            ),
            ephemeral=True,
        )
        return None

    @classmethod
    async def build_suggest_modal(
        cls,
        *,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ):
        components = [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "commands.suggest.options.suggestion.name", ctx
                ).capitalize(),
                description=localisations.get_localized_string(
                    "commands.suggest.options.suggestion.description", ctx
                ),
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
                    label=localisations.get_localized_string(
                        "commands.suggest.options.image.name", ctx
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "commands.suggest.options.image.description", ctx
                    ),
                    component=hikari.impl.FileUploadComponentBuilder(
                        custom_id="files",
                        min_values=1,
                        max_values=5,
                        is_required=False,
                    ),
                )
            )

        if guild_config.can_have_anonymous_suggestions:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label=localisations.get_localized_string(
                        "commands.suggest.options.anonymously.name", ctx
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "commands.suggest.options.anonymously.description", ctx
                    ),
                    component=hikari.impl.TextSelectMenuBuilder(
                        custom_id="anonymously",
                        parent=None,
                        options=[
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.suggestion.yes",
                                    ctx,
                                ),
                                value="yes",
                            ),
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.suggestion.no",
                                    ctx,
                                ),
                                value="no",
                                is_default=True,
                            ),
                        ],
                        min_values=1,
                        max_values=1,
                        is_required=False,
                    ),
                )
            )

        return components
