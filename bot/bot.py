import hikari
import lightbulb
import logoo
from hikari.impl import CacheSettings, config

from bot.localisation import Localisation
from bot.tables import GuildConfig, UserConfig

logger = logoo.Logger(__name__)


async def create_guild_config(ctx: lightbulb.Context) -> GuildConfig:
    gc: GuildConfig = await GuildConfig.objects().get_or_create(
        GuildConfig.id == ctx.guild_id  # type: ignore
    )
    if gc._was_created:
        logger.debug("Created new GuildConfig for %s", ctx.guild_id)

    return gc


async def create_user_config(ctx: lightbulb.Context) -> UserConfig:
    uc: UserConfig = await UserConfig.objects().get_or_create(
        UserConfig.id == ctx.user.id  # type: ignore
    )
    if uc._was_created:
        logger.debug("Created new UserConfig for %s", ctx.user.id)

    return uc


async def create_bot(token) -> (hikari.GatewayBot, lightbulb.Client):
    bot = hikari.GatewayBot(
        token=token,
        cache_settings=CacheSettings(components=config.CacheComponents.NONE),
        intents=hikari.Intents.NONE,
    )
    localisations = Localisation()
    client = lightbulb.client_from_app(bot)
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        GuildConfig, create_guild_config
    )
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        UserConfig, create_user_config
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
