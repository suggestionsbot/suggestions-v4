import logging

import hikari
import lightbulb

from bot.constants import CONFIGURE_GROUP
from bot.localisation import Localisation
from bot.menus.guild_configuration_menu import GuildConfigurationMenus
from shared.tables import GuildConfigs, UserConfigs

logger = logging.getLogger(__name__)


@CONFIGURE_GROUP.register
class ConfigureGuildCmd(
    lightbulb.SlashCommand,
    name="commands.configure.guild.name",
    description="commands.configure.guild.description",
    localize=True,
):
    menu = lightbulb.string(
        "commands.configure.guild.options.menu.name",
        "commands.configure.guild.options.menu.description",
        localize=True,
        default="commands.configure.guild.options.menu.choices.1.name",
        choices=[
            lightbulb.Choice(
                "commands.configure.guild.options.menu.choices.1.name",
                "overall",
                True,
            ),
            lightbulb.Choice(
                "commands.configure.guild.options.menu.choices.2.name",
                "log_channel",
                True,
            ),
            lightbulb.Choice(
                "commands.configure.guild.options.menu.choices.3.name",
                "queue_settings",
                True,
            ),
        ],
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if self.menu == "log_channel":
            components = await GuildConfigurationMenus.build_log_channel_components(
                ctx=ctx, guild_config=guild_config, localisations=localisations
            )
        elif self.menu == "queue_settings":
            components = await GuildConfigurationMenus.build_queue_components(
                ctx=ctx, guild_config=guild_config, localisations=localisations
            )
        else:
            components = await GuildConfigurationMenus.build_base_components_page_1(
                ctx=ctx, guild_config=guild_config, localisations=localisations
            )
        await ctx.respond(components=components)
