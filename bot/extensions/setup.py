import logging

import hikari
import lightbulb

from bot.hooks import early_ephemeral_defer
from bot.localisation import Localisation
from bot.menus.guild_configuration_menu import GuildConfigurationMenus
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import GuildConfigs, UserConfigs

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


@loader.command
class SetupCmd(
    lightbulb.SlashCommand,
    name="commands.setup.name",
    description="commands.setup.description",
    localize=True,
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
    contexts=[hikari.ApplicationContextType.GUILD],
    hooks=[early_ephemeral_defer],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/setup",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        # This command is really just a fast path to GCM so we dont
        # need to reinvent the wheel here
        components = await GuildConfigurationMenus.build_setup_components(
            ctx=ctx,
            guild_config=guild_config,
            localisations=localisations,
            user_config=user_config,
        )
        await ctx.respond(components=components)
