from pathlib import Path

import hikari
import lightbulb
import logoo
from hikari.impl import CacheSettings, config

from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs, PremiumGuildConfigs
from shared.utils import configs

logger = logoo.Logger(__name__)


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
    client = lightbulb.client_from_app(
        bot,
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
        # TODO Implement
        await ctx.respond("Something went wrong")
        return False

    return bot, client
