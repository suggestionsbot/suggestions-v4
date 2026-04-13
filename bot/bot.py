import asyncio
import logging

import hikari
import lightbulb
from hikari.impl import CacheSettings, config

from bot import overrides, utils, constants
from bot.constants import OTEL_TRACER
from bot.menus import (
    GuildConfigurationMenus,
    SuggestionMenu,
    SuggestionsQueueMenu,
    SuggestionsQueueViewerMenu,
)
from shared.tables import GuildConfigs, UserConfigs
from shared.utils import configs
from web import constants as t_constants

logger = logging.getLogger(__name__)


async def create_guild_config(ctx: lightbulb.Context) -> GuildConfigs:
    return await configs.ensure_guild_config(ctx.guild_id)


async def create_user_config(ctx: lightbulb.Context) -> UserConfigs:
    return await configs.ensure_user_config(ctx.user.id, locale=ctx.interaction.locale)


async def create_bot(
    token, *, log_conf: str | None = "INFO"
) -> (hikari.GatewayBot, lightbulb.Client):
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
    logger.debug(f"Test with {repr(log_conf)}")

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
        GuildConfigs, create_guild_config
    )
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        UserConfigs, create_user_config
    )
    from bot.localisation import Localisation

    client.di.registry_for(lightbulb.di.Contexts.DEFAULT).register_value(
        Localisation, constants.LOCALISATIONS
    )

    @client.error_handler
    async def handler(
        exc: lightbulb.exceptions.ExecutionPipelineFailedException,
        ctx: lightbulb.Context,
    ) -> bool:
        if not ctx.initial_response_sent.is_set():
            # If we have yet to send some form of response
            await ctx.defer(ephemeral=True)

        with utils.start_error_span(exc.causes[0], "global error handler"):
            # TODO Implement
            await ctx.respond("Something went wrong")

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
            otel_ctx = await utils.otel.get_context_from_link_state(
                custom_id.split(":", maxsplit=1)[1]
            )

        with OTEL_TRACER.start_as_current_span(component_key, otel_ctx) as span:
            span.set_attribute("interaction.user.id", ctx.user.id)
            span.set_attribute(
                "interaction.user.global_name",
                (ctx.user.global_name if ctx.user.global_name else ctx.user.username),
            )
            if ctx.guild_id:
                span.set_attribute("interaction.guild.id", ctx.guild_id)

            guild_config = await configs.ensure_guild_config(ctx.guild_id)
            user_config = await configs.ensure_user_config(ctx.user.id)
            await SuggestionMenu.handle_interaction(
                event.interaction.components,
                ctx=ctx,
                localisations=constants.LOCALISATIONS,
                event=event,
                guild_config=guild_config,
                user_config=user_config,
            )

    def build_ctx(
        interaction: hikari.ComponentInteraction | hikari.ModalInteraction,
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
    async def on_component_interaction(
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

        elif custom_id.startswith("queue_approve") or custom_id.startswith(
            "queue_approve"
        ):
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
                ":", maxsplit=4
            )
            queued_suggestion_id = queued_suggestion_id if queued_suggestion_id else None
            otel_ctx = await utils.otel.get_context_from_link_state(link_id)
            component_key = f"queue paginator {action}"

        elif custom_id.startswith("suggestions_up_vote") or custom_id.startswith(
            "suggestions_down_vote"
        ):
            # Legacy button type one
            custom_id, suggestion_id = custom_id.split("|", maxsplit=2)
            custom_id = custom_id[:-1]
            vote_enum = (
                SuggestionsVoteTypeEnum.UpVote
                if custom_id == "suggestions_up_vote"
                else SuggestionsVoteTypeEnum.DownVote
            )
            component_key = f"suggestion {vote_enum.value}"

        elif custom_id.startswith("SuggestionsUpVote") or custom_id.startswith(
            "SuggestionsDownVote"
        ):
            # Other legacy button type
            custom_id, suggestion_id = custom_id.split(":", maxsplit=2)
            vote_enum = (
                SuggestionsVoteTypeEnum.UpVote
                if custom_id == "SuggestionsUpVote"
                else SuggestionsVoteTypeEnum.DownVote
            )
            component_key = f"suggestion {vote_enum.value}"

        elif custom_id.startswith("v4_suggestions_up_vote") or custom_id.startswith(
            "v4_suggestions_down_vote"
        ):
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
                (ctx.user.global_name if ctx.user.global_name else ctx.user.username),
            )
            if ctx.guild_id:
                span.set_attribute("interaction.guild.id", ctx.guild_id)

            if custom_id.startswith("gcm"):
                guild_config = await configs.ensure_guild_config(ctx.guild_id)
                _, link_id, setting = custom_id.split(":", maxsplit=2)
                await GuildConfigurationMenus.handle_interaction(
                    setting,
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                    guild_config=guild_config,
                    link_id=link_id,
                )

            elif custom_id.startswith("v4_queue:"):
                await SuggestionsQueueViewerMenu.handle_paginator_interaction(
                    queue_id=pid,  # noqa
                    action=action,  # noqa
                    queued_suggestion_id=queued_suggestion_id,  # noqa
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                )

            elif component_key in ("queue approve", "queue reject"):
                guild_config = await configs.ensure_guild_config(ctx.guild_id)
                await SuggestionsQueueMenu.handle_physical_interaction(
                    queued_suggestion_id,  # noqa
                    to_approve,  # noqa
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                    event=event,
                    guild_config=guild_config,
                )

            elif component_key in ("suggestion UpVote", "suggestion DownVote"):
                await SuggestionMenu.handle_vote(
                    suggestion_id,  # noqa
                    vote_enum,  # noqa
                    ctx=ctx,
                    localisations=constants.LOCALISATIONS,
                )

            else:
                await ctx.respond(
                    embed=utils.error_embed(
                        "Unknown Event",
                        "Please contact support if this keeps happening "
                        "and describe what you did before seeing this error.",
                    ),
                    ephemeral=True,
                )

    return bot, client
