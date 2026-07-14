import io
import logging
from typing import cast

import hikari
import lightbulb

import shared.utils
from bot import utils
from bot.constants import NOTES_GROUP, EMBED_COLOR
from bot.hooks import early_ephemeral_defer
from bot.localisation import Localisation
from bot.tables import CommandTypes, CommandInvokes
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
            "Not dm'ing %s for a note changed on "
            "suggestion %s as they have dm's disabled",
            suggestion.author_id,
            suggestion.sID,
            extra={
                "interaction.guild.id": ctx.guild_id,
                "suggestion.id": suggestion.sID,
                "interaction.author.id": suggestion.author_id,
            },
        )
        return

    if guild_config.generic_dm_messages_disabled:
        logger.debug(
            "Not dm'ing %s for a note changed on "
            "suggestion %s as the guilds has dm's disabled",
            suggestion.author_id,
            suggestion.sID,
            extra={
                "interaction.guild.id": ctx.guild_id,
                "suggestion.id": suggestion.sID,
            },
        )
        return

    components: list = [
        hikari.impl.TextDisplayComponentBuilder(
            content=localisations.get_localized_string(
                "commands.note.add.responses.dm_change",
                user_config.primary_language,
                extras={"JUMP": suggestion.message_jump_link},
            ),
        ),
        hikari.impl.SeparatorComponentBuilder(
            divider=True,
            spacing=hikari.SpacingType.SMALL,
        ),
        hikari.impl.TextDisplayComponentBuilder(
            content=localisations.get_localized_string(
                "commands.note.add.responses.dm_change_footer",
                user_config.primary_language,
                guild_config=guild_config,
                extras={"GUILD_ID": guild_config.guild_id, "SID": suggestion.footer_sid},
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
        dm_channel = await ctx.client.rest.create_dm_channel(
            hikari.Snowflake(user_config.user_id)
        )
        await dm_channel.send(components=result)
    except hikari.ForbiddenError:
        # I'd consider it 'fine' if the bot can't send this message
        logger.debug(
            "Failed to dm user about a suggestion note",
            extra={
                "interaction.user.id": user_config.user_id,
                "interaction.guild.id": guild_config.guild_id,
                "suggestion.id": suggestion.sID,
            },
        )


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = str(ctx.focused.value) or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=cast("int", ctx.interaction.guild_id),
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
    hooks=[early_ephemeral_defer],
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
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        # backwards compat for newlines instead of using a modal
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/note add",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        response = io.StringIO()
        if self.anonymously and not guild_config.allow_anonymous_moderators:
            response.write(
                localisations.get_localized_string(
                    "commands.note.responses.not_allowed_anonymous",
                    user_config.primary_language,
                )
            )
            self.anonymously = False

        note = self.note.replace("\\n", "\n")
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id,
            cast("int", ctx.guild_id),
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
                        "menus.suggestion.not_found.title",
                        user_config.primary_language,
                    ),
                    localisations.get_localized_string(
                        "menus.suggestion.not_found.description",
                        user_config.primary_language,
                    ),
                ),
                ephemeral=True,
            )
            return

        suggestion.moderator_note = note
        suggestion.moderator_note_added_by = user_config.user_id
        # All moderator note authors are public
        suggestion.moderator_note_added_by_display_text = utils.generate_author_text(
            ctx.user.display_name, ctx.user.id, is_anonymous=self.anonymously
        )
        await suggestion.save()
        await suggestion.queue_message_edit()
        response.write("\n\n")
        response.write(
            localisations.get_localized_string(
                "commands.note.add.responses.change",
                user_config.primary_language,
                extras={"JUMP": suggestion.message_jump_link},
            ),
        )
        await ctx.respond(response.getvalue(), ephemeral=True)
        await notify_user_of_change(
            ctx=ctx,
            suggestion=suggestion,
            user_config=user_config,
            guild_config=guild_config,
            localisations=localisations,
        )

        return


@NOTES_GROUP.register
class NotesRemoveCmd(
    lightbulb.SlashCommand,
    name="commands.note.remove.name",
    description="commands.note.remove.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    hooks=[early_ephemeral_defer],
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
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/note remove",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id,
            cast("int", ctx.guild_id),
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
                        "menus.suggestion.not_found.title",
                        user_config.primary_language,
                    ),
                    localisations.get_localized_string(
                        "menus.suggestion.not_found.description",
                        user_config.primary_language,
                    ),
                ),
                ephemeral=True,
            )
            return

        suggestion.moderator_note = None
        suggestion.moderator_note_added_by = None
        suggestion.moderator_note_added_by_display_text = None
        await suggestion.save()
        await suggestion.queue_message_edit()
        await ctx.respond(
            localisations.get_localized_string(
                "commands.note.add.responses.change",
                user_config.primary_language,
                extras={"JUMP": suggestion.message_jump_link},
            ),
            ephemeral=True,
        )
        await notify_user_of_change(
            ctx=ctx,
            suggestion=suggestion,
            user_config=user_config,
            guild_config=guild_config,
            localisations=localisations,
        )

        return
