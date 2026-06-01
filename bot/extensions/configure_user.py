import logging

import lightbulb

from bot.constants import CONFIGURE_GROUP
from bot.localisation import Localisation
from bot.menus.user_configuration_menu import UserConfigurationMenus
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import GuildConfigs, UserConfigs

logger = logging.getLogger(__name__)


@CONFIGURE_GROUP.register
class ConfigureUserCmd(
    lightbulb.SlashCommand,
    name="commands.configure.user.name",
    description="commands.configure.user.description",
    localize=True,
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/configure user",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        components = await UserConfigurationMenus.build_base_components_page_1(
            ctx=ctx,
            user_config=user_config,
            localisations=localisations,
        )
        await ctx.respond(components=components)
