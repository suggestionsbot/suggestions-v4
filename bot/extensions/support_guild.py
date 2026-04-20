import datetime
import io
import logging
import sys

import hikari
import humanize
import lightbulb
from hikari import snowflakes
from humanize import naturaldate

import shared.utils
from bot.constants import TOTAL_SHARDS, CLUSTER_ID, VERSION, EMBED_COLOR, LOADED_AT
from bot.localisation import Localisation
from bot.tables import InternalErrors
from shared.tables import GuildConfigs, UserConfigs
from shared.tables.mixins.audit import utc_now
from web.constants import IS_PRODUCTION

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)

GUILDS = [
    737166408525283348,  # Test Server
]
if IS_PRODUCTION:
    GUILDS.append(
        601219766258106399,  # Main server
    )


@loader.command(guilds=GUILDS)
class ErrorInformation(
    lightbulb.SlashCommand,
    name="commands.error_info.name",
    description="commands.error_info.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    error_id = lightbulb.string(
        "commands.error_info.options.error_id.name",
        "commands.error_info.options.error_id.description",
        localize=True,
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        bot: hikari.RESTBot | hikari.GatewayBot,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if ctx.user.id != 271612318947868673:
            await ctx.respond("I'm sorry this command is only for Ethan.")
            return None

        error: InternalErrors = await InternalErrors.objects().get(
            InternalErrors.id == self.error_id
        )
        if error is None:
            await ctx.respond("Couldn't find an error with that ID.")
            return None

        embed = hikari.Embed(
            colour=EMBED_COLOR,
            timestamp=utc_now(),
            title=f"Information for error {error.id}",
            description=f"**Command name**: `{error.command_name}`\n\n"
            f"**User ID**: `{error.user_id}` | **Guild ID**: `{error.guild_id}`\n\n"
            f"**Error**: `{error.error_name}`\n"
            f"**Error occurred**: `{naturaldate(error.created_at)}` (<t:{int(error.created_at.timestamp())}:F>)",
        )
        await ctx.respond(
            embed=embed,
            ephemeral=True,
            attachment=hikari.files.Bytes(
                io.StringIO(error.traceback),
                f"traceback-{error.id}.txt",
                mimetype="text/plain",
            ),
        )
        return None
