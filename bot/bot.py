import asyncio
import logging
from pathlib import Path

import hikari
import lightbulb
from hikari.impl import CacheSettings, config
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from bot import overrides, utils
from bot.constants import OTEL_TRACER
from bot.localisation import Localisation
from bot.menus import GuildConfigurationMenus
from shared.tables import GuildConfigs, UserConfigs
from shared.utils import configs
from web import constants as t_constants

logger = logging.getLogger(__name__)


async def create_guild_config(ctx: lightbulb.Context) -> GuildConfigs:
    return await configs.ensure_guild_config(ctx.guild_id)


async def create_user_config(ctx: lightbulb.Context) -> UserConfigs:
    return await configs.ensure_user_config(ctx.user.id)


async def create_bot(
    token, base_path: Path, *, log_conf: str | None = "INFO"
) -> (hikari.GatewayBot, lightbulb.Client):
    bot = hikari.GatewayBot(
        token=token,
        logs=log_conf,
        cache_settings=CacheSettings(components=config.CacheComponents.NONE),
        intents=hikari.Intents.NONE,
    )
    logger.debug(f"Test with {repr(log_conf)}")
    localisations = Localisation(base_path)

    default_enabled_guilds = ()
    if not t_constants.IS_PRODUCTION:
        default_enabled_guilds = (737166408525283348,)
    client = overrides.client_from_app(
        bot,
        default_enabled_guilds=default_enabled_guilds,
        default_locale=hikari.Locale.EN_GB,
        localization_provider=localisations.lightbulb_provider,
    )
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        GuildConfigs, create_guild_config
    )
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        UserConfigs, create_user_config
    )
    client.di.registry_for(lightbulb.di.Contexts.DEFAULT).register_value(
        Localisation, localisations
    )

    @client.error_handler
    async def handler(
        exc: lightbulb.exceptions.ExecutionPipelineFailedException,
        ctx: lightbulb.Context,
    ) -> bool:
        if not ctx.initial_response_sent.is_set():
            # If we have yet to send some form of response
            await ctx.defer(ephemeral=True)

        with utils.start_error_span(exc.causes[0], "global error handler") as child:
            # TODO Implement
            await ctx.respond("Something went wrong")
        return False

    def build_ctx(
        interaction: hikari.ComponentInteraction,
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
        # TODO Wrap these events in a component error handler
        ctx = build_ctx(event.interaction)
        custom_id: str = event.interaction.custom_id

        # TODO Handle legacy logic
        if ":" not in custom_id:
            # Not a handled custom button so let it go
            return

        # TODO Handle legacy logic
        component_key = f"component {custom_id}"
        if custom_id.startswith("gcm"):
            component_key = (
                f"editing guild setting '{custom_id.split(':',maxsplit=1)[1]}'"
            )

        with OTEL_TRACER.start_as_current_span(component_key) as span:
            span.set_attribute("interaction.user.id", ctx.user.id)
            span.set_attribute(
                "interaction.user.global_name",
                (ctx.user.global_name if ctx.user.global_name else ctx.user.username),
            )
            if ctx.guild_id:
                span.set_attribute("interaction.guild.id", ctx.guild_id)

            if custom_id.startswith("gcm"):
                guild_config = await configs.ensure_guild_config(ctx.guild_id)
                await GuildConfigurationMenus.handle_interaction(
                    custom_id.split(":", maxsplit=1)[1],
                    ctx=ctx,
                    localisations=localisations,
                    event=event,
                    guild_config=guild_config,
                )

        await ctx.defer(ephemeral=True)

    return bot, client
