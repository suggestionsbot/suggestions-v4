import logging

import hikari
import lightbulb

import shared.utils
from bot import utils
from bot.constants import BLOCKLIST_GROUP
from bot.localisation import Localisation
from shared.tables import (
    GuildConfigs,
    Suggestions,
    QueuedSuggestions,
)

logger = logging.getLogger(__name__)


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = ctx.focused.value or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=ctx.interaction.guild_id,
        search=current_value,
        index="shared_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


@BLOCKLIST_GROUP.register
class BlocklistAddCmd(
    lightbulb.SlashCommand,
    name="commands.blocklist.add.name",
    description="commands.blocklist.add.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.blocklist.add.options.suggestion_id.name",
        "commands.blocklist.add.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        suggestion: Suggestions | QueuedSuggestions | None = (
            await Suggestions.fetch_suggestion(self.suggestion_id, ctx.guild_id)
        )
        if suggestion is None:
            suggestion: Suggestions | QueuedSuggestions | None = (
                await QueuedSuggestions.fetch_queued_suggestion(
                    self.suggestion_id, ctx.guild_id
                )
            )
            if suggestion is None:
                logger.debug(
                    "SuggestionNotFound",
                    extra={
                        "interaction.guild.id": ctx.guild_id,
                        "interaction.author.id": ctx.user.id,
                        "interaction.author.global_name": ctx.user.global_name,
                    },
                )
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "menus.suggestion.not_found.title", ctx.interaction.locale
                        ),
                        localisations.get_localized_string(
                            "menus.suggestion.not_found.description",
                            ctx.interaction.locale,
                        ),
                    ),
                    ephemeral=True,
                )
                return None

        author_to_block: int = suggestion.author_id
        if author_to_block in guild_config.blocked_users:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.blocklist.add.responses.already_blocked",
                    ctx.interaction.locale,
                ),
                ephemeral=True,
            )
            return None

        guild_config.blocked_users.append(author_to_block)
        await guild_config.save()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.blocklist.add.responses.added_to_blocklist",
                ctx.interaction.locale,
            ),
            ephemeral=True,
        )
        logger.debug(
            "User %s added %s to the blocklist for guild %s",
            ctx.interaction.user.id,
            author_to_block,
            ctx.guild_id,
            extra={
                "interaction.author.id": ctx.interaction.user.id,
                "interaction.author.global_name": (
                    ctx.interaction.user.global_name
                    if ctx.interaction.user.global_name
                    else ""
                ),
                "interaction.guild.id": ctx.guild_id,
            },
        )
        return None


@BLOCKLIST_GROUP.register
class BlocklistRemoveCmd(
    lightbulb.SlashCommand,
    name="commands.blocklist.remove.name",
    description="commands.blocklist.remove.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.blocklist.remove.options.suggestion_id.name",
        "commands.blocklist.remove.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
        default=None,
    )
    user = lightbulb.user(
        "commands.blocklist.remove.options.user.name",
        "commands.blocklist.remove.options.user.description",
        localize=True,
        default=None,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if self.suggestion_id is None and self.user is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.blocklist.remove.responses.argument_required",
                    ctx.interaction.locale,
                ),
                ephemeral=True,
            )
            return None

        if self.suggestion_id is not None and self.user is not None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.blocklist.remove.responses.too_many_arguments",
                    ctx.interaction.locale,
                ),
                ephemeral=True,
            )
            return None

        user_to_unblock: int | None = None
        if self.user is not None:
            user_to_unblock = self.user.id

        if self.suggestion_id is not None:
            suggestion: Suggestions | QueuedSuggestions | None = (
                await Suggestions.fetch_suggestion(self.suggestion_id, ctx.guild_id)
            )
            if suggestion is None:
                suggestion: Suggestions | QueuedSuggestions | None = (
                    await QueuedSuggestions.fetch_queued_suggestion(
                        self.suggestion_id, ctx.guild_id
                    )
                )
                if suggestion is None:
                    logger.debug(
                        "SuggestionNotFound",
                        extra={
                            "interaction.guild.id": ctx.guild_id,
                            "interaction.author.id": ctx.user.id,
                            "interaction.author.global_name": ctx.user.global_name,
                        },
                    )
                    await ctx.respond(
                        embed=utils.error_embed(
                            localisations.get_localized_string(
                                "menus.suggestion.not_found.title", ctx.interaction.locale
                            ),
                            localisations.get_localized_string(
                                "menus.suggestion.not_found.description",
                                ctx.interaction.locale,
                            ),
                        ),
                        ephemeral=True,
                    )
                    return None

            user_to_unblock = suggestion.author_id

        if user_to_unblock not in guild_config.blocked_users:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.blocklist.remove.responses.not_blocked",
                    ctx.interaction.locale,
                ),
                ephemeral=True,
            )
            return None

        guild_config.blocked_users.remove(user_to_unblock)
        await guild_config.save()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.blocklist.remove.responses.now_unblocked",
                ctx.interaction.locale,
            ),
            ephemeral=True,
        )
        logger.debug(
            "User %s removed %s from the blocklist for guild %s",
            ctx.interaction.user.id,
            user_to_unblock,
            ctx.guild_id,
            extra={
                "interaction.author.id": ctx.interaction.user.id,
                "interaction.author.global_name": (
                    ctx.interaction.user.global_name
                    if ctx.interaction.user.global_name
                    else ""
                ),
                "interaction.guild.id": ctx.guild_id,
            },
        )
        return None
