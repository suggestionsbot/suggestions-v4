import logging

import hikari
import lightbulb

import shared.utils
from bot import utils
from bot.constants import NOTES_GROUP, EMBED_COLOR
from bot.localisation import Localisation
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    Suggestions,
)

logger = logging.getLogger(__name__)


async def notify_user_of_change(
    *,
    ctx: lightbulb.Context,
    user_config: UserConfigs,
    guild_config: GuildConfigs,
    suggestion: Suggestions,
    localisations: Localisation,
) -> None:
    if user_config.generic_dm_messages_disabled:
        logger.debug(
            "Not dm'ing %s for a note changed on suggestion %s as they have dm's disabled",
            suggestion.author_id,
            suggestion.sID,
            extra={
                "interaction.guild.id": ctx.guild_id,
                "suggestion.id": suggestion.sID,
                "interaction.author.id": suggestion.author_id,
            },
        )
        return None

    if guild_config.generic_dm_messages_disabled:
        logger.debug(
            "Not dm'ing %s for a note changed on suggestion %s as the guilds has dm's disabled",
            suggestion.author_id,
            suggestion.sID,
            extra={
                "interaction.guild.id": ctx.guild_id,
                "suggestion.id": suggestion.sID,
            },
        )
        return None

    components: list = [
        hikari.impl.TextDisplayComponentBuilder(
            content=localisations.get_localized_string(
                "commands.note.add.responses.dm_change",
                ctx,
                extras={"JUMP": suggestion.message_jump_link},
            )
        ),
        hikari.impl.SeparatorComponentBuilder(
            divider=True,
            spacing=hikari.SpacingType.SMALL,
        ),
        hikari.impl.TextDisplayComponentBuilder(
            content=localisations.get_localized_string(
                "commands.note.add.responses.dm_change_footer",
                ctx,
                guild_config=guild_config,
                extras={"GUILD_ID": ctx.guild_id, "SID": suggestion.footer_sid},
            ),
        ),
    ]

    result: list = [
        hikari.impl.ContainerComponentBuilder(
            accent_color=EMBED_COLOR,
            components=components,
        ),
    ]
    try:
        dm_channel = await ctx.client.rest.create_dm_channel(ctx.user)
        await dm_channel.send(components=result)
    except (hikari.ForbiddenError,):
        # I'd consider it 'fine' if the bot can't send this message
        logger.debug(
            "Failed to dm user about a suggestion note",
            extra={
                "interaction.user.id": ctx.user.id,
                "interaction.user.username": ctx.user.display_name,
                "interaction.guild.id": ctx.guild_id,
                "suggestion.id": suggestion.sID,
            },
        )


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = ctx.focused.value or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=ctx.interaction.guild_id,
        search=current_value,
        index="suggestion_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


@NOTES_GROUP.register
class NotesAddCmd(
    lightbulb.SlashCommand,
    name="commands.note.add.name",
    description="commands.note.add.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.note.add.options.suggestion_id.name",
        "commands.note.add.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )
    note = lightbulb.string(
        "commands.note.add.options.note.name",
        "commands.note.add.options.note.description",
        localize=True,
    )
    anonymously = lightbulb.boolean(
        "commands.note.options.anonymously.name",
        "commands.note.options.anonymously.description",
        default=False,
        localize=True,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        client: lightbulb.Client,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ) -> None:
        # backwards compat for newlines instead of using a modal
        await ctx.defer(ephemeral=True)
        note = self.note.replace("\\n", "\n")
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id, ctx.guild_id
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
                        "menus.suggestion.not_found.title", ctx
                    ),
                    localisations.get_localized_string(
                        "menus.suggestion.not_found.description", ctx
                    ),
                ),
                ephemeral=True,
            )
            return None

        suggestion.moderator_note = note
        suggestion.moderator_note_added_by = user_config
        # All moderator note authors are public
        suggestion.moderator_note_added_by_display_text = (
            f"<@{ctx.user.id}>" if self.anonymously is False else "Anonymous"
        )
        await suggestion.save()
        await suggestion.queue_message_edit()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.note.add.responses.change",
                ctx,
                extras={"JUMP": suggestion.message_jump_link},
            )
        )
        await notify_user_of_change(
            ctx=ctx,
            suggestion=suggestion,
            user_config=user_config,
            guild_config=guild_config,
            localisations=localisations,
        )

        return None


@NOTES_GROUP.register
class NotesRemoveCmd(
    lightbulb.SlashCommand,
    name="commands.note.remove.name",
    description="commands.note.remove.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.note.remove.options.suggestion_id.name",
        "commands.note.remove.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
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
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id, ctx.guild_id
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
                        "menus.suggestion.not_found.title", ctx
                    ),
                    localisations.get_localized_string(
                        "menus.suggestion.not_found.description", ctx
                    ),
                ),
                ephemeral=True,
            )
            return None

        suggestion.moderator_note = None
        suggestion.moderator_note_added_by = None
        suggestion.moderator_note_added_by_display_text = None
        await suggestion.save()
        await suggestion.queue_message_edit()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.note.add.responses.change",
                ctx,
                extras={"JUMP": suggestion.message_jump_link},
            )
        )
        await notify_user_of_change(
            ctx=ctx,
            suggestion=suggestion,
            user_config=user_config,
            guild_config=guild_config,
            localisations=localisations,
        )

        return None
