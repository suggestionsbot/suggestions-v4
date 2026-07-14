from __future__ import annotations

import contextlib
import io
import logging
import typing
from typing import cast, Sequence

import commons
import hikari
from hikari.interactions.interaction_components import (
    LabelInteractionComponent,  # noqa: TC002 # PR Means this may yet change
    TextInputInteractionComponent,  # noqa: TC002 # PR Means this may yet change
    FileUploadInteractionComponent,  # noqa: TC002 # PR Means this may yet change
    TextSelectMenuInteractionComponent,  # noqa: TC002 # PR Means this may yet change
)

import shared.utils
from bot import constants, utils
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MissingQueueChannel, InvalidFileType
from bot.tables import (
    InternalErrors,
    MessageAddons,
    PossibleMessageAddons,
    CommandInvokes,
    CommandTypes,
)
from bot.utils import generate_id
from shared.utils import r2, configs

if typing.TYPE_CHECKING:
    import lightbulb
    from bot.localisation import Localisation
    from shared.tables import (
        GuildConfigs,
        UserConfigs,
    )
    from shared.tables import (
        Suggestions,
        SuggestionVotes,
        SuggestionsVoteTypeEnum,
    )

logger = logging.getLogger(__name__)


class SuggestionMenu:
    @classmethod
    async def handle_embedded_button(
        cls,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
    ) -> None:
        guild_config = await configs.ensure_guild_config(cast("int", ctx.guild_id))
        user_config = await configs.ensure_user_config(ctx.user.id)
        sent_setup_message = await guild_config.ensure_config_is_setup(
            ctx=ctx, locale=user_config.primary_language
        )
        if sent_setup_message:
            return

        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="Create Suggestion",
            command_type=CommandTypes.BUTTON,
        )
        components = await cls.build_suggest_modal(
            guild_config=guild_config,
            localisations=localisations,
            ctx=ctx,
            user_config=user_config,
        )
        link_id: str = await utils.otel.generate_trace_link_state()
        await ctx.interaction.create_modal_response(
            localisations.get_localized_string(
                "commands.suggest.responses.menu_title", user_config.primary_language
            ),
            f"suggest_modal:{link_id}",
            components=components,
        )

    @classmethod
    async def handle_vote(
        cls,
        sid: str,
        vote: SuggestionsVoteTypeEnum,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        guild_config = await configs.ensure_guild_config(cast("int", ctx.guild_id))
        user_config = await configs.ensure_user_config(ctx.user.id)
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="Suggestion Vote",
            command_type=CommandTypes.BUTTON,
        )
        from shared.tables import (
            Suggestions,
            SuggestionStateEnum,
            SuggestionVotes,
            SuggestionsVoteTypeEnum,
        )

        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            sid, cast("int", ctx.guild_id)
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
                        "menus.suggestion.not_found.title", user_config.primary_language
                    ),
                    localisations.get_localized_string(
                        "menus.suggestion.not_found.description",
                        user_config.primary_language,
                    ),
                ),
                ephemeral=True,
            )
            return

        if suggestion.state != SuggestionStateEnum.PENDING:
            await ctx.respond(
                localisations.get_localized_string(
                    "values.suggestion_no_more_casting", user_config.primary_language
                ),
                ephemeral=True,
            )
            return

        async with SuggestionVotes._meta.db.transaction():
            was_created = False
            try_insert = (
                await SuggestionVotes.insert(
                    SuggestionVotes(
                        suggestion=suggestion,
                        vote_type=vote,
                        user_id=ctx.user.id,
                    ),
                )
                .on_conflict(
                    action="DO NOTHING",
                    target=(SuggestionVotes.user_id, SuggestionVotes.suggestion),
                )
                .returning(*SuggestionVotes.all_columns())
            )
            if try_insert:
                vote_obj: SuggestionVotes = SuggestionVotes(**try_insert[0])
                vote_obj._exists_in_db = True
                was_created = True

            else:
                vote_obj: SuggestionVotes = (
                    await SuggestionVotes.objects()
                    .first()
                    .where(SuggestionVotes.suggestion == suggestion)
                    .where(SuggestionVotes.user_id == ctx.user.id)
                )

            if not was_created and vote_obj.vote_type == vote.value:
                # Trying to vote again for the same item
                key = (
                    "values.suggestion_up_vote_already_voted"
                    if vote == SuggestionsVoteTypeEnum.UpVote
                    else "values.suggestion_down_vote_already_voted"
                )
                await ctx.respond(
                    localisations.get_localized_string(key, user_config.primary_language),
                    ephemeral=True,
                )
                return

            if was_created:
                # New vote
                key = (
                    "values.suggestion_up_vote_registered_vote"
                    if vote == SuggestionsVoteTypeEnum.UpVote
                    else "values.suggestion_down_vote_registered_vote"
                )
                logger.debug(
                    "Member voted on %s with %s",
                    suggestion.sID,
                    vote.value,
                    extra={
                        "interaction.user.id": ctx.user.id,
                        "interaction.user.username": ctx.user.display_name,
                        "interaction.guild.id": ctx.guild_id,
                        "suggestion.id": suggestion.sID,
                    },
                )

            else:
                # Vote has changed
                key = (
                    "values.suggestion_down_vote_modified_vote"
                    if vote == SuggestionsVoteTypeEnum.DownVote
                    else "values.suggestion_up_vote_modified_vote"
                )
                logger.debug(
                    "Member modified their vote on %s to a %s",
                    suggestion.sID,
                    vote.value,
                    extra={
                        "interaction.user.id": ctx.user.id,
                        "interaction.user.username": ctx.user.display_name,
                        "interaction.guild.id": ctx.guild_id,
                        "suggestion.id": suggestion.sID,
                    },
                )

            vote_obj.vote_type_enum = vote
            await vote_obj.save()

        await suggestion.queue_message_edit()

        content = io.StringIO()
        content.write(
            localisations.get_localized_string(key, user_config.primary_language)
        )
        if (
            ma := await MessageAddons.get_message(
                user_config,
                hint=PossibleMessageAddons.SUGGESTION_RESOLUTION_NOTIFICATIONS,
            )
        ) is not None:
            content.write("\n\n")
            content.write(await ma.as_string())

        await ctx.respond(content.getvalue(), ephemeral=True)
        return

    @classmethod
    async def handle_interaction(  # noqa: PLR0912, C901
        cls,
        response_fields: Sequence[LabelInteractionComponent],
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        event: hikari.ModalInteractionCreateEvent,
    ) -> Suggestions | None:
        suggestion_content: str | None = None
        image_urls: list[str] = []
        anonymously: bool = False
        has_bad_file: bool = False
        for entry in response_fields:
            if entry.component.custom_id == "suggestion":
                entry.component = cast(
                    "TextInputInteractionComponent",
                    entry.component,
                )
                suggestion_content = entry.component.value

            elif entry.component.custom_id == "anonymously":
                entry.component = cast(
                    "FileUploadInteractionComponent",
                    entry.component,
                )
                anonymously = False
                if entry.component.values:
                    # anon by default unless you provide the value
                    anonymously = commons.value_to_bool(entry.component.values[0])

            elif entry.component.custom_id == "files":
                entry.component = cast(
                    "TextSelectMenuInteractionComponent",
                    entry.component,
                )
                if guild_config.can_have_images_in_suggestions is False:
                    await ctx.respond(
                        localisations.get_localized_string(
                            "values.suggest.no_images_in_suggestions",
                            user_config.primary_language,
                        ),
                        ephemeral=True,
                    )
                    return None

                for item_id in entry.component.values:
                    assert event.interaction.resolved is not None
                    item: hikari.messages.Attachment | None = (
                        event.interaction.resolved.attachments.get(
                            cast("hikari.Snowflake", item_id)
                        )
                    )
                    if item is None:
                        logger.critical(
                            "failed to find an image in the resolved attachments",
                        )
                        continue

                    try:
                        image_urls.append(
                            await r2.upload_file_to_r2(
                                file_name=item.filename,
                                # TODO try optimise this to do image streaming?
                                file_data=await item.read(),
                                guild_id=guild_config.guild_id,
                                user_id=user_config.user_id,
                            ),
                        )
                    except InvalidFileType:
                        # TODO Rework to delete already uploaded images if last uploaded fails
                        has_bad_file = True

        assert suggestion_content is not None
        if len(suggestion_content) > MAX_CONTENT_LENGTH:
            await ctx.respond(
                embed=utils.error_embed(
                    localisations.get_localized_string(
                        "errors.suggest.content_too_long.title",
                        user_config.primary_language,
                    ),
                    localisations.get_localized_string(
                        "errors.suggest.content_too_long.description",
                        user_config.primary_language,
                        extras={"MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH},
                    ),
                    error_code=ErrorCode.SUGGESTION_CONTENT_TOO_LONG,
                ),
                attachment=hikari.files.Bytes(
                    io.StringIO(suggestion_content),
                    "content.txt",
                ),
                ephemeral=True,
            )
            return None

        if has_bad_file:
            await ctx.respond(
                localisations.get_localized_string(
                    "values.suggest.allowed_image_types",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return None

        if anonymously is True and guild_config.can_have_anonymous_suggestions is False:
            await ctx.respond(
                localisations.get_localized_string(
                    "values.suggest.no_anonymous_suggestions",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return None

        if guild_config.uses_suggestion_queue:
            return await cls.handle_queued_suggestion(
                suggestion=suggestion_content,
                image_urls=image_urls,
                is_anonymous=anonymously,
                ctx=ctx,
                guild_config=guild_config,
                user_config=user_config,
                localisations=localisations,
            )

        return await cls.handle_suggestion(
            suggestion=suggestion_content,
            image_urls=image_urls,
            author_display_name=utils.generate_author_text(
                ctx.user.display_name, ctx.user.id, is_anonymous=anonymously
            ),
            ctx=ctx,
            guild_config=guild_config,
            user_config=user_config,
            localisations=localisations,
        )

    @classmethod
    async def handle_suggestion(
        cls,
        *,
        suggestion: str,
        image_urls: list[str],
        author_display_name: str,
        ctx: lightbulb.components.MenuContext,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        send_final_response: bool = True,
    ) -> Suggestions | None:
        """Specific helper for handling suggestions."""
        bot = ctx.client.app
        from shared.tables import SuggestionStateEnum
        from shared.tables import Suggestions

        s: Suggestions = Suggestions(
            guild_configuration=guild_config,
            user_configuration=user_config,
            suggestion=suggestion,
            image_urls=image_urls,
            author_display_name=author_display_name,
            state_raw=SuggestionStateEnum.PENDING,
            sID=generate_id(),
        )
        await s.save()  # This is needed for components

        if guild_config.suggestions_channel_id is None:
            await ctx.respond(
                embed=utils.error_embed(
                    localisations.get_localized_string(
                        "errors.suggest.suggest_channel_not_found.title",
                        user_config.primary_language,
                    ),
                    localisations.get_localized_string(
                        "errors.suggest.suggest_channel_not_found.description",
                        user_config.primary_language,
                    ),
                    error_code=ErrorCode.MISSING_FETCH_PERMISSIONS_IN_SUGGESTIONS_CHANNEL,
                ),
                ephemeral=True,
            )
            await s.delete().where(Suggestions.id == s.id)
            return None

        try:
            channel = await bot.rest.fetch_channel(guild_config.suggestions_channel_id)
            channel = cast("hikari.GuildTextChannel", channel)
        except (hikari.ForbiddenError, hikari.NotFoundError):
            await ctx.respond(
                embed=utils.error_embed(
                    localisations.get_localized_string(
                        "errors.suggest.suggest_channel_not_found.title",
                        user_config.primary_language,
                    ),
                    localisations.get_localized_string(
                        "errors.suggest.suggest_channel_not_found.description",
                        user_config.primary_language,
                    ),
                    error_code=ErrorCode.MISSING_FETCH_PERMISSIONS_IN_SUGGESTIONS_CHANNEL,
                ),
                ephemeral=True,
            )
            await s.delete().where(Suggestions.id == s.id)
            return None

        prefix = (
            guild_config.premium.suggestions_prefix
            if await guild_config.premium_is_enabled(ctx)
            and guild_config.premium.queued_suggestions_prefix is not None
            else ""
        )
        try:
            message: hikari.Message = await channel.send(
                content=prefix,
                components=await s.as_components(
                    rest=bot.rest,
                    locale=guild_config.primary_language,
                    localisations=localisations,
                    guild_config=guild_config,
                ),
            )
        except hikari.ForbiddenError as e:
            internal_error: InternalErrors = await InternalErrors.persist_error(
                e,
                command_name="suggest",
                guild_id=cast("int", ctx.guild_id),
                user_id=ctx.user.id,
            )
            await ctx.respond(
                embed=utils.error_embed(
                    title=localisations.get_localized_string(
                        "errors.suggest.responses.missing_suggestion_channel_perms.title",
                        user_config.primary_language,
                    ),
                    description=localisations.get_localized_string(
                        "errors.suggest.responses.missing_suggestion_channel_perms.description",
                        user_config.primary_language,
                    ),
                    internal_error_reference=internal_error,
                )
            )
            await s.delete().where(Suggestions.id == s.id)
            return None

        s.channel_id = message.channel_id
        s.message_id = message.id
        await s.save()
        await shared.utils.cache_sid_in_autocomplete(
            guild_id=cast("int", ctx.guild_id),
            suggestion_id=s.sID,
            index="shared_sid_autocomplete_index",
        )
        await shared.utils.cache_sid_in_autocomplete(
            guild_id=cast("int", ctx.guild_id),
            suggestion_id=s.sID,
            index="suggestion_sid_autocomplete_index",
        )

        if guild_config.threads_for_suggestions:
            try:
                thread = await bot.rest.create_message_thread(
                    channel,
                    message,
                    f"Thread for suggestion {s.sID}",
                )
                s.thread_id = thread.id
                await s.save()
            except (hikari.ForbiddenError, hikari.NotFoundError):
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "errors.suggest.missing_create_thread_perms.title",
                            user_config.primary_language,
                        ),
                        localisations.get_localized_string(
                            "errors.suggest.missing_create_thread_perms.description",
                            user_config.primary_language,
                        ),
                        error_code=ErrorCode.MISSING_THREAD_CREATE_PERMISSIONS,
                    ),
                    ephemeral=True,
                )
                await s.delete().where(Suggestions.id == s.id)
                return None

            if (
                guild_config.ping_on_thread_creation
                and user_config.ping_on_thread_creation
                and not s.is_anonymous
            ):
                # I'd consider it 'fine' if the bot can't send this message
                with contextlib.suppress(hikari.ForbiddenError, hikari.NotFoundError):
                    await thread.send(
                        localisations.get_localized_string(
                            "values.suggest.ping_author_in_thread",
                            guild_config.primary_language,
                            extras={"AUTHOR": s.author_display_name},
                        ),
                        user_mentions=True,
                    )

        await s.notify_users_of_new_suggestion()
        if send_final_response:
            # We only want to send on /suggest and not queued suggestions
            content = io.StringIO()
            content.write(
                localisations.get_localized_string(
                    "values.suggest.suggestion_sent",
                    user_config.primary_language,
                    extras={
                        "AUTHOR": s.author_display_name,
                        "CHANNEL": channel.mention,
                        "SID": s.sID,
                    },
                ),
            )
            if (ma := await MessageAddons.get_message(user_config)) is not None:
                content.write("\n\n\n")
                content.write(await ma.as_string())

            await ctx.respond(content.getvalue(), ephemeral=True)

        logger.debug(
            "Created new suggestion in guild %s",
            ctx.guild_id,
            extra={
                "interaction.user.id": ctx.user.id,
                "interaction.guild.id": ctx.guild_id,
            },
        )
        return s

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
    ) -> None:
        """Specific helper for handling queued suggestions."""
        bot = ctx.client.app
        from shared.tables import QueuedSuggestions

        qs: QueuedSuggestions = QueuedSuggestions(
            guild_configuration=guild_config,
            user_configuration=user_config,
            suggestion=suggestion,
            image_urls=image_urls,
            author_display_name=utils.generate_author_text(
                ctx.user.display_name, ctx.user.id, is_anonymous=is_anonymous
            ),
            sID=generate_id(),
        )
        await qs.save()

        if guild_config.virtual_suggestions_queue is False:
            # Need to send to a channel
            if guild_config.queued_suggestion_channel_id is None:
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "errors.suggest.missing_queue_channel.title",
                            user_config.primary_language,
                        ),
                        localisations.get_localized_string(
                            "errors.suggest.missing_queue_channel.description",
                            user_config.primary_language,
                        ),
                        error_code=ErrorCode.MISSING_QUEUE_CHANNEL,
                    ),
                    ephemeral=True,
                )
                return

            try:
                channel = await bot.rest.fetch_channel(
                    guild_config.queued_suggestion_channel_id,
                )
                channel = cast("hikari.GuildTextChannel", channel)
            except (hikari.ForbiddenError, hikari.NotFoundError):
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "errors.suggest.queue_channel_not_found.title",
                            user_config.primary_language,
                        ),
                        localisations.get_localized_string(
                            "errors.suggest.queue_channel_not_found.description",
                            user_config.primary_language,
                        ),
                        error_code=ErrorCode.MISSING_PERMISSIONS_IN_QUEUE_CHANNEL,
                    ),
                    ephemeral=True,
                )
                return

            prefix = (
                guild_config.premium.queued_suggestions_prefix
                if await guild_config.premium_is_enabled(ctx)
                else hikari.undefined.UNDEFINED
            )
            try:
                message: hikari.Message = await channel.send(
                    content=prefix,
                    components=await qs.as_components(
                        rest=bot.rest,
                        locale=guild_config.primary_language,
                        localisations=localisations,
                    ),
                )
            except hikari.ForbiddenError as e:
                internal_error: InternalErrors = await InternalErrors.persist_error(
                    e,
                    command_name="suggest",
                    guild_id=cast("int", ctx.guild_id),
                    user_id=ctx.user.id,
                )
                await ctx.respond(
                    embed=utils.error_embed(
                        title=localisations.get_localized_string(
                            "errors.suggest.responses.missing_queue_channel_perms.title",
                            user_config.primary_language,
                        ),
                        description=localisations.get_localized_string(
                            "errors.suggest.responses.missing_queue_channel_perms.description",
                            user_config.primary_language,
                        ),
                        internal_error_reference=internal_error,
                    )
                )
                await qs.delete().where(QueuedSuggestions.id == qs.id)
                return

            qs.channel_id = message.channel_id
            qs.message_id = message.id

        await qs.save()
        await shared.utils.cache_sid_in_autocomplete(
            guild_id=cast("int", ctx.guild_id),
            suggestion_id=qs.sID,
            index="shared_sid_autocomplete_index",
        )
        await shared.utils.cache_sid_in_autocomplete(
            guild_id=cast("int", ctx.guild_id),
            suggestion_id=qs.sID,
            index="queue_sid_autocomplete_index",
        )

        logger.debug(
            "Created new queued suggestion in guild %s",
            ctx.guild_id,
            extra={
                "interaction.user.id": ctx.user.id,
                "interaction.guild.id": ctx.guild_id,
            },
        )

        content = io.StringIO()
        content.write(
            localisations.get_localized_string(
                "values.suggest.sent_to_queue",
                user_config.primary_language,
                guild_config=guild_config,
            ),
        )
        if (ma := await MessageAddons.get_message(user_config)) is not None:
            content.write("\n\n\n")
            content.write(await ma.as_string())

        await ctx.respond(content.getvalue(), ephemeral=True)
        return

    @classmethod
    async def build_suggest_modal(
        cls,
        *,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> list[hikari.impl.LabelComponentBuilder]:
        components = [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "commands.suggest.options.suggestion.name",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "commands.suggest.options.suggestion.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="suggestion",
                    style=hikari.TextInputStyle.PARAGRAPH,
                    required=True,
                    min_length=1,
                    max_length=constants.MAX_CONTENT_LENGTH,
                    label="suggestion",
                ),
            ),
        ]
        if guild_config.can_have_images_in_suggestions:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label=localisations.get_localized_string(
                        "commands.suggest.options.image.name",
                        user_config.primary_language,
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "commands.suggest.options.image.description",
                        user_config.primary_language,
                    ),
                    component=hikari.impl.FileUploadComponentBuilder(
                        custom_id="files",
                        min_values=1,
                        max_values=5,
                        is_required=False,
                    ),
                ),
            )

        if guild_config.can_have_anonymous_suggestions:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label=localisations.get_localized_string(
                        "commands.suggest.options.anonymously.name",
                        user_config.primary_language,
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "commands.suggest.options.anonymously.description",
                        user_config.primary_language,
                    ),
                    component=hikari.impl.TextSelectMenuBuilder(
                        custom_id="anonymously",
                        parent=None,
                        options=[
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.suggestion.yes",
                                    user_config.primary_language,
                                ),
                                value="yes",
                            ),
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.suggestion.no",
                                    user_config.primary_language,
                                ),
                                value="no",
                                is_default=True,
                            ),
                        ],
                        min_values=1,
                        max_values=1,
                        is_required=True,
                    ),
                ),
            )

        return components
