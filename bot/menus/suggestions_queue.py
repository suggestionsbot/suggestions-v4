import io
from typing import cast

import hikari
import lightbulb
from piccolo.columns import Where, And
from piccolo.columns.operators import Equal

from bot import utils
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
    async def handle_physical_interaction(
        cls,
        queued_suggestion_id: str | None,
        to_approve: bool,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        event: hikari.ComponentInteractionCreateEvent,
    ) -> None:
        await ctx.defer(ephemeral=True)
        async with UserConfigs._meta.db.transaction():
            user_config: UserConfigs = await configs.ensure_user_config(
                user_id=event.interaction.user.id,
                locale=event.interaction.locale,
            )
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

            else:
                queued_suggestion = await QueuedSuggestions.fetch_queued_suggestion(
                    queued_suggestion_id,
                    cast("int", event.interaction.guild_id),
                    lock_rows=True,
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
    ) -> None:
        queued_suggestion.state = QueuedSuggestionStateEnum.APPROVED
        queued_suggestion.resolved_at = utc_now()
        queued_suggestion.resolved_by = event.interaction.user.id
        queued_suggestion.resolved_by_display_text = (
            f"<@{ctx.user.id}>"
            if guild_config.allow_anonymous_moderators is False
            else "Anonymous"
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
    ) -> None:
        # needs rejecting
        queued_suggestion.state = QueuedSuggestionStateEnum.REJECTED
        queued_suggestion.resolved_at = utc_now()
        queued_suggestion.resolved_by = event.interaction.user.id
        queued_suggestion.resolved_by_display_text = (
            f"<@{ctx.user.id}>"
            if guild_config.allow_anonymous_moderators is False
            else "Anonymous"
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
