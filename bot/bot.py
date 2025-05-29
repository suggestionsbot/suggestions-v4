import hikari
import lightbulb
from hikari.impl import CacheSettings, config

from bot.tables import GuildConfig


async def create_guild_config(ctx: lightbulb.Context) -> GuildConfig:
    gc: GuildConfig = await GuildConfig.objects().get_or_create(
        GuildConfig.id == ctx.guild_id
    )
    if gc._was_created:
        # Debug log a new guild config was created
        pass

    return gc


async def create_bot(token) -> (hikari.GatewayBot, lightbulb.Client):
    bot = hikari.GatewayBot(
        token=token,
        cache_settings=CacheSettings(components=config.CacheComponents.NONE),
        intents=hikari.Intents.NONE,
    )
    client = lightbulb.client_from_app(bot)
    client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
        GuildConfig, create_guild_config
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
