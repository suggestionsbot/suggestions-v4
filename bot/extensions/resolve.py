import logging
from typing import cast

import hikari
import lightbulb

import shared
from bot.localisation import Localisation
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    Suggestions,
    SuggestionStateEnum,
)
from web.util.table_mixins import utc_now

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


async def resolve_suggestion(
    suggestion: Suggestions,
    response: str | None,
    anonymously: bool,
    suggestion_state: SuggestionStateEnum,
    ctx: lightbulb.Context,
    guild_config: GuildConfigs,
    user_config: UserConfigs,
    localisations: Localisation,
) -> None:
    logger.debug(
        "Attempting to resolve suggestion %s",
        suggestion.sID,
        extra={
            "suggestion.id": suggestion.sID,
            "interaction.guild.id": guild_config.guild_id,
        },
    )
    suggestion.state_raw = suggestion_state
    suggestion.resolved_at = utc_now()
    suggestion.resolved_note = response
    suggestion.resolved_by = user_config.user_id
    suggestion.resolved_by_display_text = (
        f"<@{ctx.user.id}>" if anonymously is False else "Anonymous"
    )

    # Archive thread if required
    if guild_config.auto_archive_threads and suggestion.thread_id:
        try:
            thread = await ctx.client.rest.fetch_channel(suggestion.thread_id)
            thread = cast(hikari.GuildThreadChannel, thread)
        except (hikari.NotFoundError,):
            # While not ideal, we ignore the error here as
            # failing to archive a thread isn't a critical issue
            # worth crashing on. Instead, pass this to the actual
            # suggestion closing logic to handle more gracefully
            #
            # It'll likely still fail there but like, meh. Failing
            # to find the thread here means technically the function worked
            pass

        else:
            if not thread.is_archived and not thread.is_locked:
                # Thread is not already archived or locked
                await thread.send(
                    localisations.get_localized_string(
                        "commands.resolve.responses.locking_thread",
                        ctx.interaction.locale,
                    )
                )
                await thread.edit(locked=True, archived=True)
                logger.debug(
                    "Locked thread for suggestion %s",
                    suggestion.sID,
                    extra={
                        "suggestion.id": suggestion.sID,
                        "interaction.guild.id": guild_config.guild_id,
                    },
                )

    # Edit message inline with guild configuration
    if guild_config.keep_logs:
        # Simple! The Dream.
        await suggestion.save()
        await suggestion.queue_message_edit(exclude_buttons=True, as_resolved=True)
        await suggestion.notify_users_of_resolution()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.keep_logs_edit_soon",
                ctx.interaction.locale,
                extras={"SID": suggestion.sID},
            )
        )
        return None

    # Need to delete from the original channel and move to new one
    try:
        log_channel = await ctx.client.rest.fetch_channel(guild_config.log_channel_id)
        log_channel = cast(hikari.GuildTextChannel, log_channel)
    except (hikari.NotFoundError, hikari.ForbiddenError):
        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.cant_get_log_channel", ctx.interaction.locale
            )
        )
        return None

    try:
        components = await suggestion.as_components(
            guild_config=guild_config,
            locale=guild_config.primary_language,
            rest=ctx.client.rest,
            localisations=localisations,
            exclude_buttons=True,
            as_resolved=True,
        )
        log_message = await log_channel.send(components=components)
    except (hikari.NotFoundError, hikari.ForbiddenError):
        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.cant_get_log_channel", ctx.interaction.locale
            )
        )
        return None

    try:
        original_suggestion_message: hikari.Message = await ctx.client.rest.fetch_message(
            suggestion.channel_id, suggestion.message_id
        )
    except (hikari.NotFoundError, hikari.ForbiddenError):
        # Looks like the original was deleted
        # But eh thats fine as we can make our new log anyway
        pass
    else:
        try:
            await original_suggestion_message.delete()
        except hikari.ForbiddenError:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.resolve.responses.missing_suggestion_channel_perms",
                    ctx.interaction.locale,
                ),
            )

    suggestion.channel_id = log_message.channel_id
    suggestion.message_id = log_message.id
    await suggestion.save()
    await suggestion.notify_users_of_resolution()
    await ctx.respond(
        localisations.get_localized_string(
            "commands.resolve.responses.resolved_immediately",
            ctx.interaction.locale,
            extras={"SID": suggestion.sID, "JUMP": suggestion.message_jump_link},
        )
    )
    return None


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = ctx.focused.value or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=ctx.interaction.guild_id,
        search=current_value,
        index="shared_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


@loader.command
class ResolveCmd(
    lightbulb.SlashCommand,
    name="commands.resolve.name",
    description="commands.resolve.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.resolve.options.suggestion_id.name",
        "commands.resolve.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )
    resolution_state_raw = lightbulb.string(
        "commands.resolve.options.resolution.name",
        "commands.resolve.options.resolution.description",
        localize=True,
        choices=[
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.1.name",
                "Approved",
                True,
            ),
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.2.name",
                "Rejected",
                True,
            ),
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.3.name",
                "Implemented",
                True,
            ),
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.4.name",
                "Duplicate",
                True,
            ),
        ],
    )
    response = lightbulb.string(
        "commands.resolve.options.response.name",
        "commands.resolve.options.response.description",
        localize=True,
        default=None,
    )
    anonymously = lightbulb.boolean(
        "commands.resolve.options.anonymously.name",
        "commands.resolve.options.anonymously.description",
        default=False,
        localize=True,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        note: str | None = (
            self.response.replace("\\n", "\n") if self.response is not None else None
        )
        state: SuggestionStateEnum = SuggestionStateEnum(self.resolution_state_raw)
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id, guild_config.guild_id
        )
        if suggestion:
            await resolve_suggestion(
                suggestion,
                note,
                self.anonymously,
                state,
                ctx,
                guild_config,
                user_config,
                localisations,
            )
            return

        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.suggestion_not_found", ctx.interaction.locale
            )
        )


@loader.command
class ApproveCmd(
    lightbulb.SlashCommand,
    name="commands.approve.name",
    description="commands.approve.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.approve.options.suggestion_id.name",
        "commands.approve.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )
    response = lightbulb.string(
        "commands.approve.options.response.name",
        "commands.approve.options.response.description",
        localize=True,
        default=None,
    )
    anonymously = lightbulb.boolean(
        "commands.approve.options.anonymously.name",
        "commands.approve.options.anonymously.description",
        default=False,
        localize=True,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        note: str | None = (
            self.response.replace("\\n", "\n") if self.response is not None else None
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id, guild_config.guild_id
        )
        if suggestion:
            await resolve_suggestion(
                suggestion,
                note,
                self.anonymously,
                SuggestionStateEnum.APPROVED,
                ctx,
                guild_config,
                user_config,
                localisations,
            )
            return

        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.suggestion_not_found", ctx.interaction.locale
            )
        )


@loader.command
class RejectCmd(
    lightbulb.SlashCommand,
    name="commands.reject.name",
    description="commands.reject.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.reject.options.suggestion_id.name",
        "commands.reject.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )
    response = lightbulb.string(
        "commands.reject.options.response.name",
        "commands.reject.options.response.description",
        localize=True,
        default=None,
    )
    anonymously = lightbulb.boolean(
        "commands.reject.options.anonymously.name",
        "commands.reject.options.anonymously.description",
        default=False,
        localize=True,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        note: str | None = (
            self.response.replace("\\n", "\n") if self.response is not None else None
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id, guild_config.guild_id
        )
        if suggestion:
            await resolve_suggestion(
                suggestion,
                note,
                self.anonymously,
                SuggestionStateEnum.REJECTED,
                ctx,
                guild_config,
                user_config,
                localisations,
            )
            return

        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.suggestion_not_found", ctx.interaction.locale
            )
        )
