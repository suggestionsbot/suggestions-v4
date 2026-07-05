import io
import logging
from typing import cast

import hikari
import lightbulb

import shared.utils
from bot import constants, utils
from bot.localisation import Localisation
from bot.tables import MessageAddons, PossibleMessageAddons, CommandTypes, CommandInvokes
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    Suggestions,
    SuggestionStateEnum,
)
from web.util.table_mixins import utc_now

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


async def resolve_suggestion(  # noqa: PLR0915, PLR0912, C901
    suggestion: Suggestions,
    response: str | None,
    anonymously: bool,
    suggestion_state: SuggestionStateEnum,
    ctx: lightbulb.Context | lightbulb.components.MenuContext,
    guild_config: GuildConfigs,
    user_config: UserConfigs,
    localisations: Localisation,
    apply_message_addon: bool = False,
) -> None:
    logger.debug(
        "Attempting to resolve suggestion %s",
        suggestion.sID,
        extra={
            "suggestion.id": suggestion.sID,
            "interaction.guild.id": guild_config.guild_id,
        },
    )
    content = io.StringIO()
    if anonymously and not guild_config.allow_anonymous_moderators:
        content.write(
            localisations.get_localized_string(
                "commands.resolve.responses.not_allowed_anonymous",
                user_config.primary_language,
            )
        )
        content.write("\n\n")
        anonymously = False

    suggestion.state = suggestion_state
    suggestion.resolved_at = utc_now()
    suggestion.resolved_note = response
    suggestion.resolved_by = user_config.user_id
    suggestion.resolved_by_display_text = (
        f"<@{ctx.user.id}>" if anonymously is False else "Anonymous"
    )
    await suggestion.save()

    # Archive thread if required
    if guild_config.auto_archive_threads and suggestion.thread_id:
        try:
            thread = await ctx.client.rest.fetch_channel(suggestion.thread_id)
            thread = cast("hikari.GuildThreadChannel", thread)
        except hikari.NotFoundError:
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
                        guild_config.primary_language,
                    ),
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
        content.write(
            localisations.get_localized_string(
                "commands.resolve.responses.keep_logs_edit_soon",
                user_config.primary_language,
                extras={"SID": suggestion.sID},
            ),
        )
        if (
            apply_message_addon
            and (
                ma := await MessageAddons.get_message(
                    user_config,
                    hint=PossibleMessageAddons.LEGACY_RESOLUTION_COMMANDS,
                )
            )
            is not None
        ):
            content.write("\n\n")
            content.write(await ma.as_string())

        await ctx.respond(content.getvalue())
        return

    # Need to delete from the original channel and move to new one
    if guild_config.log_channel_id is None:
        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.no_log_channel",
                user_config.primary_language,
            ),
            ephemeral=True,
        )
        return

    try:
        log_channel = await ctx.client.rest.fetch_channel(guild_config.log_channel_id)
        log_channel = cast("hikari.GuildTextChannel", log_channel)
    except (hikari.NotFoundError, hikari.ForbiddenError):
        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.cant_get_log_channel",
                user_config.primary_language,
            ),
            ephemeral=True,
        )
        return

    try:
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
        except hikari.ClientHTTPResponseError:
            components = await suggestion.as_components(
                guild_config=guild_config,
                locale=guild_config.primary_language,
                rest=ctx.client.rest,
                localisations=localisations,
                exclude_buttons=True,
                as_resolved=True,
                skip_user_avatar=True,
            )
            log_message = await log_channel.send(components=components)
    except (hikari.NotFoundError, hikari.ForbiddenError):
        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.cant_get_log_channel",
                user_config.primary_language,
            ),
            ephemeral=True,
        )
        return

    try:
        original_suggestion_message: hikari.Message | None = None
        if suggestion.channel_id is not None and suggestion.message_id is not None:
            original_suggestion_message: hikari.Message = (
                await ctx.client.rest.fetch_message(
                    suggestion.channel_id,
                    suggestion.message_id,
                )
            )
    except (hikari.NotFoundError, hikari.ForbiddenError):
        # Looks like the original was deleted
        # But eh thats fine as we can make our new log anyway
        pass
    else:
        try:
            if original_suggestion_message is not None:
                await original_suggestion_message.delete()
        except hikari.ForbiddenError:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.resolve.responses.missing_suggestion_channel_perms",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )

    suggestion.channel_id = log_message.channel_id
    suggestion.message_id = log_message.id
    await suggestion.save()
    await suggestion.notify_users_of_resolution()
    content.write(
        localisations.get_localized_string(
            "commands.resolve.responses.resolved_immediately",
            user_config.primary_language,
            extras={"SID": suggestion.sID, "JUMP": suggestion.message_jump_link},
        ),
    )
    if (
        apply_message_addon
        and (
            ma := await MessageAddons.get_message(
                user_config,
                hint=PossibleMessageAddons.LEGACY_RESOLUTION_COMMANDS,
            )
        )
        is not None
    ):
        content.write("\n\n")
        content.write(await ma.as_string())

    await ctx.respond(content.getvalue(), ephemeral=True)
    return


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = str(ctx.focused.value) or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=cast("int", ctx.interaction.guild_id),
        search=current_value,
        index="suggestion_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


@loader.command
class ResolveCmd(
    lightbulb.SlashCommand,
    name="commands.resolve.name",
    description="commands.resolve.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
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
                localize=True,
            ),
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.2.name",
                "Rejected",
                localize=True,
            ),
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.3.name",
                "Implemented",
                localize=True,
            ),
            lightbulb.Choice(
                "commands.resolve.options.resolution.menu.choices.4.name",
                "Duplicate",
                localize=True,
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
        sent_setup_message = await guild_config.ensure_config_is_setup(
            ctx=ctx, locale=user_config.primary_language
        )
        if sent_setup_message:
            return

        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/resolve",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        note: str | None = (
            self.response.replace("\\n", "\n") if self.response is not None else None
        )
        state: SuggestionStateEnum = SuggestionStateEnum(self.resolution_state_raw)
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id,
            guild_config.guild_id,
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
                "commands.resolve.responses.suggestion_not_found",
                user_config.primary_language,
            ),
            ephemeral=True,
        )


@loader.command
class ApproveCmd(
    lightbulb.SlashCommand,
    name="commands.approve.name",
    description="commands.approve.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
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
        sent_setup_message = await guild_config.ensure_config_is_setup(
            ctx=ctx, locale=user_config.primary_language
        )
        if sent_setup_message:
            return

        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/approve",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        note: str | None = (
            self.response.replace("\\n", "\n") if self.response is not None else None
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id,
            guild_config.guild_id,
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
                apply_message_addon=True,
            )
            return

        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.suggestion_not_found",
                user_config.primary_language,
            ),
            ephemeral=True,
        )


@loader.command
class RejectCmd(
    lightbulb.SlashCommand,
    name="commands.reject.name",
    description="commands.reject.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
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
        sent_setup_message = await guild_config.ensure_config_is_setup(
            ctx=ctx, locale=user_config.primary_language
        )
        if sent_setup_message:
            return

        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/reject",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        note: str | None = (
            self.response.replace("\\n", "\n") if self.response is not None else None
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id,
            guild_config.guild_id,
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
                apply_message_addon=True,
            )
            return

        await ctx.respond(
            localisations.get_localized_string(
                "commands.resolve.responses.suggestion_not_found",
                user_config.primary_language,
            ),
            ephemeral=True,
        )


class ResolveMessageCommand(
    lightbulb.MessageCommand,
    name="message_commands.resolve.name",
    localize=True,
):
    @classmethod
    async def build_resolve_modal(
        cls,
        *,
        user_configs: UserConfigs,
        localisations: Localisation,
    ) -> list[hikari.impl.LabelComponentBuilder]:
        components = [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "commands.resolve.options.resolution.name",
                    user_configs.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "commands.resolve.options.resolution.description",
                    user_configs.primary_language,
                ),
                component=hikari.impl.TextSelectMenuBuilder(
                    custom_id="resolution_state_raw",
                    parent=None,
                    options=[
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "commands.resolve.options.resolution.menu.choices.1.name",
                                user_configs.primary_language,
                            ),
                            value="Approved",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "commands.resolve.options.resolution.menu.choices.2.name",
                                user_configs.primary_language,
                            ),
                            value="Rejected",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "commands.resolve.options.resolution.menu.choices.3.name",
                                user_configs.primary_language,
                            ),
                            value="Implemented",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "commands.resolve.options.resolution.menu.choices.4.name",
                                user_configs.primary_language,
                            ),
                            value="Duplicate",
                        ),
                    ],
                    is_required=True,
                    min_values=1,
                    max_values=1,
                ),
            ),
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "commands.resolve.options.response.name",
                    user_configs.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "commands.resolve.options.response.description",
                    user_configs.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="response",
                    style=hikari.TextInputStyle.PARAGRAPH,
                    required=False,
                    min_length=1,
                    max_length=constants.MAX_CONTENT_LENGTH,
                    label="response",
                ),
            ),
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "commands.resolve.options.anonymously.name",
                    user_configs.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "commands.resolve.options.anonymously.description",
                    user_configs.primary_language,
                ),
                component=hikari.impl.TextSelectMenuBuilder(
                    custom_id="anonymously",
                    parent=None,
                    options=[
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.resolve.yes",
                                user_configs.primary_language,
                            ),
                            value="yes",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.resolve.no",
                                user_configs.primary_language,
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
        ]

        return components

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        user_config: UserConfigs,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> None:
        # 'self.target' contains the message object the command was executed on
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="Resolve Suggestion",
            command_type=CommandTypes.MESSAGE_COMMAND,
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion_by_message(
            channel_id=self.target.channel_id,
            message_id=self.target.id,
            guild_id=guild_config.guild_id,
        )
        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.resolve.responses.suggestion_not_found",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return

        components = await self.build_resolve_modal(
            localisations=localisations, user_configs=user_config
        )

        link_id: str = await utils.otel.generate_trace_link_state()
        await ctx.respond_with_modal(
            localisations.get_localized_string(
                "message_commands.resolve.name",
                user_config.primary_language,
            ),
            f"resolve_modal:{link_id}:{suggestion.sID}",
            components=components,
        )
        return
