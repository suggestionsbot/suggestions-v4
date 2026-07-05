import io
import logging
from typing import cast

import hikari
import lightbulb

from bot import utils, menus
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MessageTooLong, MissingQueueChannel
from bot.localisation import Localisation
from bot.tables import InternalErrors, CommandInvokes, CommandTypes
from shared.tables import GuildConfigs, UserConfigs

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


@loader.command
class Suggest(
    lightbulb.SlashCommand,
    name="commands.suggest.name",
    description="commands.suggest.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        sent_setup_message = await guild_config.ensure_config_is_setup(
            ctx=ctx,
            locale=user_config.primary_language,
            # Dont need logs in suggest
            # We assume if suggest button that someone has
            # already done the configuration though so we only do this here
            skip_log_channel_check=True,
        )
        if sent_setup_message:
            return

        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/suggest",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        if ctx.user.id in guild_config.blocked_users:
            await ctx.respond(
                embed=utils.error_embed(
                    localisations.get_localized_string(
                        "commands.suggest.responses.blocked.title",
                        user_config.primary_language,
                    ),
                    localisations.get_localized_string(
                        "commands.suggest.responses.blocked.description",
                        user_config.primary_language,
                    ),
                ),
                ephemeral=True,
            )
            return

        components = await menus.SuggestionMenu.build_suggest_modal(
            guild_config=guild_config,
            localisations=localisations,
            ctx=ctx,
            user_config=user_config,
        )

        link_id: str = await utils.otel.generate_trace_link_state()
        await ctx.respond_with_modal(
            localisations.get_localized_string(
                "commands.suggest.responses.menu_title",
                user_config.primary_language,
            ),
            f"suggest_modal:{link_id}",
            components=components,
        )
        return
