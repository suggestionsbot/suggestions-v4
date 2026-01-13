import logging
from typing import Sequence

import hikari
import lightbulb
from hikari.api import special_endpoints

from bot.localisation import Localisation
from bot.menus.guild_configuration_menu import GuildConfigurationMenus
from shared.tables import GuildConfigs, UserConfigs

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


def handle_configure_errors(func):
    func = lightbulb.di.with_di(func)

    async def _wrapper(
        command_data,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ):
        try:
            return await func(
                command_data,
                ctx=ctx,
                bot=bot,
                guild_config=guild_config,
                user_config=user_config,
                localisations=localisations,
            )
        except Exception as exception:
            raise

    return _wrapper


@loader.command
class Configure(
    lightbulb.SlashCommand,
    name="commands.configure.name",
    description="commands.configure.description",
    localize=True,
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
    contexts=[hikari.ApplicationContextType.GUILD],
):

    @lightbulb.invoke
    @handle_configure_errors
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ) -> None:
        await ctx.defer(ephemeral=True)
        components = await GuildConfigurationMenus.build_base_components(
            ctx=ctx, guild_config=guild_config, localisations=localisations
        )
        await ctx.respond(components=components)
