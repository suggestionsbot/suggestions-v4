import io
from typing import cast

import hikari
import lightbulb
from piccolo.columns import Where, And
from piccolo.columns.operators import Equal

from bot import utils, constants
from bot.localisation import Localisation
from bot.menus import SuggestionMenu
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import (
    GuildConfigs,
    QueuedSuggestions,
    UserConfigs,
    QueuedSuggestionStateEnum,
    Suggestions,
)
from shared.tables.mixins.audit import utc_now
from shared.utils import configs


class SuggestionsQueueMenu:
    @classmethod
    async def build_queue_modal(
        cls,
        to_approve: bool,
        localisations: Localisation,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
    ):
        components = [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.queue_resolve.options.state.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.queue_resolve.options.state.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextSelectMenuBuilder(
                    custom_id="state",
                    parent=None,
                    options=[
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.queue_resolve.options.state.approve",
                                user_config.primary_language,
                            ),
                            value="approve",
                            is_default=to_approve,
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.queue_resolve.options.state.reject",
                                user_config.primary_language,
                            ),
                            value="reject",
                            is_default=not to_approve,
                        ),
                    ],
                    min_values=1,
                    max_values=1,
                    is_required=True,
                ),
            ),
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.queue_resolve.options.note.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.queue_resolve.options.note.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="response",
                    style=hikari.TextInputStyle.PARAGRAPH,
                    required=False,
                    min_length=1,
                    max_length=constants.MAX_CONTENT_LENGTH,
                    label="note",
                ),
            ),
        ]

        if guild_config.allow_anonymous_moderators:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label=localisations.get_localized_string(
                        "menus.queue_resolve.options.anonymously.title",
                        user_config.primary_language,
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "menus.queue_resolve.options.anonymously.description",
                        user_config.primary_language,
                    ),
                    component=hikari.impl.TextSelectMenuBuilder(
                        custom_id="anonymously",
                        parent=None,
                        options=[
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.queue_resolve.yes",
                                    user_config.primary_language,
                                ),
                                value="yes",
                            ),
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.queue_resolve.no",
                                    user_config.primary_language,
                                ),
                                value="no",
                                is_default=True,
                            ),
                        ],
                        min_values=1,
                        max_values=1,
                        is_required=False,
                    ),
                ),
            )

        return components

    @classmethod
    async def handle_physical_interaction(
        cls,
        queued_suggestion_id: str | None,
        to_approve: bool,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        event: hikari.ComponentInteractionCreateEvent,
    ) -> None:
        user_config = await configs.ensure_user_config(cast("int", ctx.user.id))
        guild_config = await configs.ensure_guild_config(cast("int", ctx.guild_id))
        if queued_suggestion_id is None:
            # Legacy events did not contain the id
            queued_suggestion = (
                await QueuedSuggestions.objects(
                    QueuedSuggestions.user_configuration,
                    QueuedSuggestions.guild_configuration,
                    QueuedSuggestions.related_suggestion,
                )
                .lock_rows("NO KEY UPDATE", of=(QueuedSuggestions,))
                .get(
                    And(
                        Where(
                            QueuedSuggestions.channel_id,
                            event.interaction.channel_id,
                            operator=Equal,
                        ),
                        Where(
                            QueuedSuggestions.message_id,
                            event.interaction.message.id,
                            operator=Equal,
                        ),
                    ),
                )
            )

        elif isinstance(queued_suggestion_id, QueuedSuggestions):
            queued_suggestion = queued_suggestion_id

        else:
            queued_suggestion = await QueuedSuggestions.fetch_queued_suggestion(
                queued_suggestion_id,
                cast("int", event.interaction.guild_id),
                lock_rows=True,
            )

        if queued_suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.queue.responses.missing",
                    user_config.primary_language,
                ),
            )
            return

        components = await cls.build_queue_modal(
            guild_config=guild_config,
            localisations=localisations,
            user_config=user_config,
            to_approve=to_approve,
        )

        link_id: str = await utils.otel.generate_trace_link_state()
        await ctx.respond_with_modal(
            localisations.get_localized_string(
                "menus.resolve_queued.responses.menu_title",
                user_config.primary_language,
            ),
            f"queue_resolve_modal:{link_id}:{queued_suggestion.id}",
            components=components,
        )
        return

    @classmethod
    async def handle_modal_interaction(
        cls,
        queued_suggestion_id: str,
        to_approve: bool,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        event: hikari.ComponentInteractionCreateEvent,
        reason: str | None = None,
        anonymously: bool = False,
    ) -> None:
        await ctx.defer(ephemeral=True)
        async with UserConfigs._meta.db.transaction():
            user_config: UserConfigs = await configs.ensure_user_config(
                user_id=event.interaction.user.id,
                locale=event.interaction.locale,
            )
            queued_suggestion = await QueuedSuggestions.objects(
                QueuedSuggestions.user_configuration,
                QueuedSuggestions.guild_configuration,
            ).get(
                # This is the PK here not sID
                QueuedSuggestions.id
                == int(queued_suggestion_id)
            )

            await CommandInvokes.create(
                user_config=user_config,
                guild_config=guild_config,
                action=f"Suggestions Queue {'Approve' if to_approve else 'Reject'}",
                command_type=CommandTypes.BUTTON,
            )

            if queued_suggestion is None:
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.queue.responses.missing",
                        user_config.primary_language,
                    ),
                )
                return

            if not to_approve:
                key = "menus.queue.responses.rejected"
                await cls.reject_queued_suggestion(
                    queued_suggestion,
                    ctx=ctx,
                    localisations=localisations,
                    guild_config=guild_config,
                    event=event,
                    user_config=user_config,
                    resolved_note=reason,
                    is_anonymous=anonymously,
                )

            else:
                key = "menus.queue.responses.approved"
                await cls.approve_queued_suggestion(
                    queued_suggestion,
                    ctx=ctx,
                    localisations=localisations,
                    guild_config=guild_config,
                    event=event,
                    user_config=user_config,
                    resolved_note=reason,
                    is_anonymous=anonymously,
                )

            message: io.StringIO = io.StringIO()
            message.write(
                localisations.get_localized_string(
                    key,
                    user_config.primary_language,
                ),
            )
            did_delete = await queued_suggestion.remove_queued_suggestion(ctx)
            if not did_delete:
                message.write("\n\n")
                message.write(
                    localisations.get_localized_string(
                        "commands.resolve.responses.missing_queued_suggestion_channel_perms",
                        user_config.primary_language,
                    ),
                )
            await ctx.respond(message.getvalue())

    @classmethod
    async def approve_queued_suggestion(
        cls,
        queued_suggestion: QueuedSuggestions,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        event: hikari.ComponentInteractionCreateEvent,
        resolved_note: str | None,
        is_anonymous: bool,
    ) -> None:
        queued_suggestion.state = QueuedSuggestionStateEnum.APPROVED
        queued_suggestion.resolved_at = utc_now()
        queued_suggestion.resolved_by = event.interaction.user.id
        queued_suggestion.resolved_note = resolved_note
        queued_suggestion.resolved_by_display_text = (
            f"<@{ctx.user.id}>" if is_anonymous is False else "Anonymous"
        )
        await queued_suggestion.save()
        suggestion: Suggestions | None = await SuggestionMenu.handle_suggestion(
            suggestion=queued_suggestion.suggestion,
            image_urls=queued_suggestion.image_urls,
            author_display_name=queued_suggestion.author_display_name,
            ctx=ctx,
            guild_config=queued_suggestion.guild_configuration,
            user_config=queued_suggestion.user_configuration,
            localisations=localisations,
            send_final_response=False,
        )
        if suggestion is None:
            # upstream errored in a handled way
            return

        queued_suggestion.related_suggestion = suggestion
        await queued_suggestion.save()
        await queued_suggestion.notify_users_of_resolution()

    @classmethod
    async def reject_queued_suggestion(
        cls,
        queued_suggestion: QueuedSuggestions,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        event: hikari.ComponentInteractionCreateEvent,
        resolved_note: str | None,
        is_anonymous: bool,
    ) -> None:
        # needs rejecting
        queued_suggestion.state = QueuedSuggestionStateEnum.REJECTED
        queued_suggestion.resolved_at = utc_now()
        queued_suggestion.resolved_by = event.interaction.user.id
        queued_suggestion.resolved_note = resolved_note
        queued_suggestion.resolved_by_display_text = (
            f"<@{ctx.user.id}>" if is_anonymous is False else "Anonymous"
        )
        await queued_suggestion.save()
        if queued_suggestion.is_physical:
            # Delete from channel
            try:
                await event.interaction.app.rest.delete_message(
                    channel=hikari.Snowflake(queued_suggestion.channel_id),
                    message=hikari.Snowflake(queued_suggestion.message_id),
                )
                queued_suggestion.channel_id = None
                queued_suggestion.message_id = None
            except hikari.NotFoundError:
                # Good, already gone
                pass
            except hikari.ForbiddenError:
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "menus.queue.responses.queue_channel_no_perms.title",
                            user_config.primary_language,
                        ),
                        localisations.get_localized_string(
                            "menus.queue.responses.queue_channel_no_perms.description",
                            user_config.primary_language,
                        ),
                    ),
                    ephemeral=True,
                )
                return

        # We may need to send to a log channel
        if guild_config.queued_suggestion_log_channel_id:
            components = await queued_suggestion.as_components(
                event.interaction.app.rest,
                guild_config.primary_language,
                localisations,
                include_buttons=False,
            )
            try:
                await event.interaction.app.rest.create_message(
                    hikari.Snowflake(guild_config.queued_suggestion_log_channel_id),
                    components=components,
                )

            except (hikari.NotFoundError, hikari.ForbiddenError):
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "menus.queue.responses.queue_log_channel_not_found.title",
                            user_config.primary_language,
                        ),
                        localisations.get_localized_string(
                            "menus.queue.responses.queue_log_channel_not_found.description",
                            user_config.primary_language,
                        ),
                    ),
                    ephemeral=True,
                )
                return

        await queued_suggestion.save()
        await queued_suggestion.notify_users_of_resolution()
