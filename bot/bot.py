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
from shared.tables import GuildConfigs, UserConfigs
from shared.utils import configs
from web import constants as t_constants

logger = logging.getLogger(__name__)


async def create_guild_config(ctx: lightbulb.Context) -> GuildConfigs:
    return await configs.ensure_guild_config(ctx.guild_id)


async def create_user_config(ctx: lightbulb.Context) -> UserConfigs:
    return await configs.ensure_user_config(ctx.user.id)


async def create_bot(token, base_path: Path) -> (hikari.GatewayBot, lightbulb.Client):
    bot = hikari.GatewayBot(
        token=token,
        cache_settings=CacheSettings(components=config.CacheComponents.NONE),
        intents=hikari.Intents.NONE,
    )
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
        with utils.start_error_span(exc.causes[0], "global error handler") as child:
            # TODO Implement
            await ctx.respond("Something went wrong")
        return False

    return bot, client
