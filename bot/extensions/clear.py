import logging

import hikari
import lightbulb

import shared
from bot.localisation import Localisation
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    Suggestions,
    SuggestionStateEnum,
    QueuedSuggestions,
    QueuedSuggestionStateEnum,
)
from web.util.table_mixins import utc_now

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = ctx.focused.value or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=ctx.interaction.guild_id,
        search=current_value,
        index="shared_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


@loader.command
class ClearCmd(
    lightbulb.SlashCommand,
    name="commands.clear.name",
    description="commands.clear.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
):
    suggestion_id = lightbulb.string(
        "commands.clear.options.suggestion_id.name",
        "commands.clear.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )
    response = lightbulb.string(
        "commands.clear.options.response.name",
        "commands.clear.options.response.description",
        localize=True,
        default=None,
    )
    anonymously = lightbulb.boolean(
        "commands.clear.options.anonymously.name",
        "commands.clear.options.anonymously.description",
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
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/clear",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        suggestion: Suggestions | QueuedSuggestions | None = (
            await Suggestions.fetch_suggestion(self.suggestion_id, guild_config.guild_id)
        )
        if suggestion is None:
            suggestion = await QueuedSuggestions.fetch_queued_suggestion(
                self.suggestion_id, guild_config.guild_id
            )

        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.clear.responses.not_found", user_config.primary_language
                ),
                ephemeral=True,
            )
            return None

        if suggestion.channel_id and suggestion.message_id:
            # Try to delete
            try:
                await ctx.client.rest.delete_message(
                    suggestion.channel_id, suggestion.message_id
                )
                suggestion.message_id = None
                suggestion.channel_id = None
            except hikari.HikariError:
                # This is fine
                pass

        suggestion.resolved_by = user_config.user_id
        suggestion.resolved_by_display_text = (
            "Anonymous" if self.anonymously else f"<@{user_config.user_id}>"
        )
        suggestion.resolved_note = self.response
        suggestion.resolved_at = utc_now()
        if isinstance(suggestion, Suggestions):
            suggestion.state = SuggestionStateEnum.CLEARED
        elif isinstance(suggestion, QueuedSuggestions):
            suggestion.state = QueuedSuggestionStateEnum.CLEARED

        await suggestion.save()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.clear.responses.cleared",
                user_config.primary_language,
                extras={"SID": suggestion.sID},
            ),
            ephemeral=True,
        )
        return None
