import logging

import hikari
import lightbulb

from bot import utils
from bot.constants import CONFIGURE_GROUP
from bot.localisation import Localisation
from bot.menus.guild_configuration_menu import GuildConfigurationMenus
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import GuildConfigs, UserConfigs
from shared.utils import set_cached_interaction_id

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
                localize=True,
            ),
            lightbulb.Choice(
                "commands.configure.guild.options.menu.choices.2.name",
                "log_channel",
                localize=True,
            ),
            lightbulb.Choice(
                "commands.configure.guild.options.menu.choices.3.name",
                "queue_settings",
                localize=True,
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
    ) -> None:
        await ctx.defer(ephemeral=True)
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/configure guild",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        link_id = await utils.otel.generate_trace_link_state()
        if self.menu == "log_channel":
            components = await GuildConfigurationMenus.build_log_channel_components(
                ctx=ctx,
                guild_config=guild_config,
                localisations=localisations,
                link_id=link_id,
            )
        elif self.menu == "queue_settings":
            components = await GuildConfigurationMenus.build_queue_components(
                ctx=ctx,
                guild_config=guild_config,
                localisations=localisations,
                link_id=link_id,
            )
        else:
            components = await GuildConfigurationMenus.build_base_components_page_1(
                ctx=ctx,
                guild_config=guild_config,
                localisations=localisations,
                link_id=link_id,
            )

        resp = await ctx.respond(components=components)
        await set_cached_interaction_id(link_id, resp)
