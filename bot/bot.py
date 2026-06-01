import asyncio
import logging
from typing import cast, Literal

import commons
import hikari
import lightbulb
from hikari.impl import CacheSettings, config
from hikari.interactions.interaction_components import (
    TextInputInteractionComponent,
    FileUploadInteractionComponent,
)

from bot import overrides, utils, constants
from bot.constants import OTEL_TRACER, LOCALISATIONS
from bot.extensions.resolve import resolve_suggestion
from bot.menus import (
    GuildConfigurationMenus,
    SuggestionMenu,
    SuggestionsQueueMenu,
    SuggestionsQueueViewerMenu,
    UserConfigurationMenus,
)
from bot.tables import InternalErrors
from shared.tables import GuildConfigs, UserConfigs, Suggestions, SuggestionStateEnum
from shared.utils import configs
from web import constants as t_constants

logger = logging.getLogger(__name__)


async def create_guild_config(ctx: lightbulb.Context) -> GuildConfigs:
    return await configs.ensure_guild_config(cast("int", ctx.guild_id))


async def create_user_config(ctx: lightbulb.Context) -> UserConfigs:
    return await configs.ensure_user_config(ctx.user.id, locale=ctx.interaction.locale)


async def create_bot(  # noqa: PLR0915, C901
    token: str,
    *,
    log_conf: str | None = "INFO",
) -> tuple[hikari.GatewayBot, lightbulb.Client]:
    intents = hikari.Intents.NONE
    intents |= hikari.Intents.GUILDS
    # We will cache guilds and see how big it gets
    cache_items = config.CacheComponents.NONE
    cache_items |= config.CacheComponents.GUILDS
    bot = hikari.GatewayBot(
        token=token,
        logs=log_conf,
        cache_settings=CacheSettings(components=cache_items),
        intents=intents,
    )

    default_enabled_guilds = ()
    if not t_constants.IS_PRODUCTION:
        default_enabled_guilds = (737166408525283348,)
    client = overrides.client_from_app(
        bot,
        default_enabled_guilds=default_enabled_guilds,
        default_locale=hikari.Locale.EN_GB,
        localization_provider=constants.LOCALISATIONS.lightbulb_provider,
    )
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        GuildConfigs,
        create_guild_config,
    )
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        UserConfigs,
        create_user_config,
    )
    from bot.localisation import Localisation

    client.di.registry_for(lightbulb.di.Contexts.DEFAULT).register_value(
        Localisation,
        constants.LOCALISATIONS,
    )

    @client.error_handler
    async def global_error_handler(
        exc: lightbulb.exceptions.ExecutionPipelineFailedException,
        ctx: lightbulb.Context,
    ) -> bool:
        if not ctx.initial_response_sent.is_set():
            # If we have yet to send some form of response
            await ctx.defer(ephemeral=True)

        with utils.start_error_span(exc.causes[0], "global error handler"):
            # TODO Implement
            internal_error: InternalErrors = await InternalErrors.persist_error(
                exc.causes[0],
                command_name=ctx.command_data.name,
                guild_id=cast("int", ctx.guild_id),
                user_id=ctx.user.id,
            )
            await ctx.respond(
                embed=utils.error_embed(
                    "Something went wrong.",
                    "Please contact support if this keeps happening.",
                    internal_error_reference=internal_error,
                ),
            )

        raise exc
        return False

    @bot.listen()
    async def modal_event(event: hikari.ModalInteractionCreateEvent) -> None:
        # event.interaction.resolved.attachments
        ctx = build_ctx(event.interaction)
        custom_id: str = event.interaction.custom_id

        otel_ctx = None
        component_key = f"{custom_id} modal"
        if custom_id.startswith("suggest_modal"):
            component_key = "suggestion modal"
            link_id = custom_id.split(":", maxsplit=1)[1]
            if link_id is not None and link_id:
                otel_ctx = await utils.otel.get_context_from_link_state(
                    custom_id.split(":", maxsplit=1)[1],
                )

        elif custom_id.startswith("resolve_modal"):
            component_key = "resolve modal"
            _, link_id, suggestion_id = custom_id.split(":", maxsplit=2)
            if link_id is not None and link_id:
                otel_ctx = await utils.otel.get_context_from_link_state(link_id)

        with OTEL_TRACER.start_as_current_span(component_key, otel_ctx) as span:
            span.set_attribute("interaction.user.id", ctx.user.id)
            span.set_attribute(
                "interaction.user.global_name",
                (ctx.user.global_name or ctx.user.username),
            )
            if ctx.guild_id:
                span.set_attribute("interaction.guild.id", ctx.guild_id)

            await ctx.defer(ephemeral=True)
            guild_config = await configs.ensure_guild_config(cast("int", ctx.guild_id))
            user_config = await configs.ensure_user_config(ctx.user.id)
            if custom_id.startswith("suggest_modal"):
                await SuggestionMenu.handle_interaction(
                    event.interaction.components,
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                    guild_config=guild_config,
                    user_config=user_config,
                )

            elif custom_id.startswith("resolve_modal"):
                suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
                    suggestion_id, guild_config.guild_id  # noqa
                )
                resolution_state_raw: str
                response: str | None = None
                anonymously: bool = False
                for entry in event.interaction.components:
                    if entry.component.custom_id == "resolution_state_raw":
                        entry.component = cast(
                            "FileUploadInteractionComponent",
                            entry.component,
                        )
                        resolution_state_raw: str = entry.component.values[0]
                    elif entry.component.custom_id == "response":
                        entry.component = cast(
                            "TextInputInteractionComponent",
                            entry.component,
                        )
                        response = entry.component.value

                    elif entry.component.custom_id == "anonymously":
                        entry.component = cast(
                            "FileUploadInteractionComponent",
                            entry.component,
                        )
                        anonymously = commons.value_to_bool(entry.component.values[0])

                # We know by here this is always true
                suggestion: Suggestions = cast("Suggestions", suggestion)
                await resolve_suggestion(
                    suggestion,
                    response,
                    anonymously,
                    SuggestionStateEnum(resolution_state_raw),
                    ctx,
                    guild_config,
                    user_config,
                    LOCALISATIONS,
                )

            else:
                await ctx.respond(
                    embed=utils.error_embed(
                        title="Unknown Modal",
                        description=f"Please reach out to support with a screenshot of this message.\n\n"
                        f"Custom ID: {custom_id}",
                    ),
                    ephemeral=True,
                )

    def build_ctx(
        interaction: (
            hikari.ComponentInteraction
            | hikari.ModalInteraction
            | hikari.CommandInteraction
        ),
    ) -> lightbulb.components.MenuContext:
        return lightbulb.components.MenuContext(
            client,
            None,  # type: ignore
            interaction,
            None,  # type: ignore
            None,  # type: ignore
            None,  # type: ignore
            asyncio.Event(),
        )

    @bot.listen(hikari.ComponentInteractionCreateEvent)
    async def on_component_interaction(  # noqa: PLR0915, PLR0912, C901
        event: hikari.ComponentInteractionCreateEvent,
    ) -> None:
        from shared.tables import SuggestionsVoteTypeEnum

        # TODO Wrap these events in a component error handler
        ctx = build_ctx(event.interaction)
        custom_id: str = event.interaction.custom_id

        # TODO Handle legacy logic
        otel_ctx = None
        component_key = f"component {custom_id}"
        if custom_id.startswith("gcm"):
            _, link_id, setting = custom_id.split(":", maxsplit=2)
            component_key = f"editing guild setting '{setting}'"
            otel_ctx = await utils.otel.get_context_from_link_state(link_id)

        elif custom_id.startswith("ucm"):
            _, link_id, setting = custom_id.split(":", maxsplit=2)
            component_key = f"editing user setting '{setting}'"
            otel_ctx = await utils.otel.get_context_from_link_state(link_id)

        elif custom_id.startswith("v4_suggest_button"):
            component_key = "creating suggestion from button"

        elif custom_id.startswith(("queue_approve", "queue_approve")):
            # Legacy physical queue
            if not custom_id.endswith("e"):
                custom_id = custom_id[:-1]

            component_key = custom_id.replace("_", " ")
            queued_suggestion_id = None
            to_approve = custom_id.endswith("approve")

        elif custom_id.startswith("v4_queued_suggestion"):
            _, approve, queued_suggestion_id = custom_id.split(":", maxsplit=2)
            to_approve = approve == "approve"
            component_key = f"queue {approve}"

        elif custom_id.startswith("v4_queue:"):
            _, action, pid, queued_suggestion_id, link_id = custom_id.split(
                ":",
                maxsplit=4,
            )
            queued_suggestion_id = queued_suggestion_id or None
            otel_ctx = await utils.otel.get_context_from_link_state(link_id)
            component_key = f"queue paginator {action}"

        elif custom_id.startswith(("suggestions_up_vote", "suggestions_down_vote")):
            # Legacy button type one
            custom_id, suggestion_id = custom_id.split("|", maxsplit=2)
            custom_id = custom_id[:-1]
            vote_enum = (
                SuggestionsVoteTypeEnum.UpVote
                if custom_id == "suggestions_up_vote"
                else SuggestionsVoteTypeEnum.DownVote
            )
            component_key = f"suggestion {vote_enum.value}"

        elif custom_id.startswith(("SuggestionsUpVote", "SuggestionsDownVote")):
            # Other legacy button type
            custom_id, suggestion_id = custom_id.split(":", maxsplit=2)
            vote_enum = (
                SuggestionsVoteTypeEnum.UpVote
                if custom_id == "SuggestionsUpVote"
                else SuggestionsVoteTypeEnum.DownVote
            )
            component_key = f"suggestion {vote_enum.value}"

        elif custom_id.startswith(("v4_suggestions_up_vote", "v4_suggestions_down_vote")):
            custom_id, suggestion_id = custom_id.split(":", maxsplit=2)
            vote_enum = (
                SuggestionsVoteTypeEnum.UpVote
                if custom_id == "v4_suggestions_up_vote"
                else SuggestionsVoteTypeEnum.DownVote
            )
            component_key = f"suggestion {vote_enum.value}"

        with OTEL_TRACER.start_as_current_span(component_key, otel_ctx) as span:
            span.set_attribute("interaction.user.id", ctx.user.id)
            span.set_attribute(
                "interaction.user.global_name",
                (ctx.user.global_name or ctx.user.username),
            )
            if ctx.guild_id:
                span.set_attribute("interaction.guild.id", ctx.guild_id)

            if custom_id.startswith("gcm"):
                _, link_id, setting = custom_id.split(":", maxsplit=2)
                await GuildConfigurationMenus.handle_interaction(
                    setting,
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                    link_id=link_id,
                )

            elif custom_id.startswith("ucm"):
                _, link_id, setting = custom_id.split(":", maxsplit=2)
                await UserConfigurationMenus.handle_interaction(
                    setting,
                    ctx=ctx,
                    event=event,
                    link_id=link_id,
                )

            elif custom_id.startswith("v4_suggest_button"):
                await SuggestionMenu.handle_embedded_button(
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                )

            elif custom_id.startswith("v4_queue:"):
                await SuggestionsQueueViewerMenu.handle_paginator_interaction(
                    queue_id=pid,
                    action=cast(
                        "Literal['back', 'next', 'stop', 'approve', 'reject']",
                        action,
                    ),
                    queued_suggestion_id=queued_suggestion_id,
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                )

            elif component_key in ("queue approve", "queue reject"):
                guild_config = await configs.ensure_guild_config(
                    cast("int", ctx.guild_id)
                )
                await SuggestionsQueueMenu.handle_physical_interaction(
                    queued_suggestion_id,
                    to_approve,
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                    guild_config=guild_config,
                )

            elif component_key in ("suggestion UpVote", "suggestion DownVote"):
                await SuggestionMenu.handle_vote(
                    suggestion_id,
                    vote_enum,
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                )

            else:
                await ctx.respond(
                    embed=utils.error_embed(
                        "Unknown Event",
                        "Please contact support if this keeps happening "
                        "and describe what you did before seeing this error."
                        f"\n\nComponent key: `{component_key}`",
                    ),
                    ephemeral=True,
                )

    return bot, client
