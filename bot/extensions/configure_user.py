import logging

import lightbulb

from bot.constants import USER_GROUP
from bot.hooks import early_ephemeral_defer
from bot.localisation import Localisation
from bot.menus.user_configuration_menu import UserConfigurationMenus
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import GuildConfigs, UserConfigs

logger = logging.getLogger(__name__)


@USER_GROUP.register
class ConfigureUserCmd(
    lightbulb.SlashCommand,
    name="commands.user.configure.name",
    description="commands.user.configure.description",
    localize=True,
    hooks=[early_ephemeral_defer],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await CommandInvokes.create(
            user_config=user_config,
            action="/configure user",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        components = await UserConfigurationMenus.build_base_components_page_1(
            user_config=user_config,
            localisations=localisations,
        )
        await ctx.respond(components=components)
