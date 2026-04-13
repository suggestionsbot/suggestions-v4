import datetime
import logging
import sys

import hikari
import humanize
import lightbulb
from hikari import snowflakes

import shared.utils
from bot.constants import TOTAL_SHARDS, CLUSTER_ID, VERSION, EMBED_COLOR, LOADED_AT
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs
from shared.tables.mixins.audit import utc_now

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


@loader.command
class InfoCmd(
    lightbulb.SlashCommand,
    name="commands.info.name",
    description="commands.info.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    support = lightbulb.boolean(
        "commands.info.options.support.name",
        "commands.info.options.support.description",
        localize=True,
        default=False,
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
        await ctx.defer(ephemeral=False)
        if self.support and guild_config.guild_id:
            shard_id = snowflakes.calculate_shard_id(TOTAL_SHARDS, guild_config.guild_id)
            shard_latency = bot._get_shard(guild_config.guild_id).heartbeat_latency
            await ctx.respond(
                f"**Guild ID:** `{guild_config.guild_id}`\n"
                f"**Cluster {CLUSTER_ID} - Shard {shard_id}:** `{round(shard_latency, 2)}ms`"
                f"**Average cluster latency:** `{round(bot.heartbeat_latency, 2)}ms`\n"
            )
            return None

        date = utc_now()
        embed: hikari.Embed = hikari.Embed(
            title=localisations.get_localized_string(
                "commands.info.responses.name", user_config.primary_language
            ),
            description=localisations.get_localized_string(
                "commands.info.responses.description", user_config.primary_language
            ),
            colour=EMBED_COLOR,
            timestamp=date,
        )
        embed.add_field(
            localisations.get_localized_string(
                "commands.info.responses.author.title", user_config.primary_language
            ),
            localisations.get_localized_string(
                "commands.info.responses.author.desc", user_config.primary_language
            ),
            inline=True,
        )
        embed.add_field(
            localisations.get_localized_string(
                "commands.info.responses.website.title", user_config.primary_language
            ),
            localisations.get_localized_string(
                "commands.info.responses.website.desc", user_config.primary_language
            ),
            inline=True,
        )
        embed.add_field(
            localisations.get_localized_string(
                "commands.info.responses.discord.title", user_config.primary_language
            ),
            localisations.get_localized_string(
                "commands.info.responses.discord.desc", user_config.primary_language
            ),
            inline=True,
        )
        embed.add_field(
            localisations.get_localized_string(
                "commands.info.responses.github.title", user_config.primary_language
            ),
            localisations.get_localized_string(
                "commands.info.responses.github.desc", user_config.primary_language
            ),
            inline=True,
        )
        embed.add_field(
            localisations.get_localized_string(
                "commands.info.responses.legal.title", user_config.primary_language
            ),
            localisations.get_localized_string(
                "commands.info.responses.legal.desc", user_config.primary_language
            ),
            inline=True,
        )
        embed.add_field(
            localisations.get_localized_string(
                "commands.info.responses.version", user_config.primary_language
            ),
            VERSION,
            inline=True,
        )
        embed.set_footer(text=f"© {date.year} Oof Software Limited")

        await ctx.respond(embed=embed)
        return None


@loader.command
class StatsCmd(
    lightbulb.SlashCommand,
    name="commands.stats.name",
    description="commands.stats.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        bot: hikari.RESTBot | hikari.GatewayBot,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=False)
        shard_id = snowflakes.calculate_shard_id(TOTAL_SHARDS, guild_config.guild_id)
        python_version = f"{sys.version_info[0]}.{sys.version_info[1]}"
        embed: hikari.Embed = hikari.Embed(
            color=EMBED_COLOR,
            timestamp=utc_now(),
        )
        if user_config.user_id == 271612318947868673:  # Skelmis
            # I want accurate stats
            guilds: int = await shared.utils.get_accurate_guild_count()
        else:
            guilds: int = (await bot.rest.fetch_application()).approximate_guild_count

        embed.add_field(
            name=localisations.get_localized_string(
                "commands.stats.responses.guild", user_config.primary_language
            ),
            value=humanize.intcomma(guilds),
            inline=True,
        )
        embed.add_field(
            name=localisations.get_localized_string(
                "commands.stats.responses.shards", user_config.primary_language
            ),
            value=TOTAL_SHARDS,
            inline=True,
        )
        embed.add_field(
            name=localisations.get_localized_string(
                "commands.stats.responses.uptime", user_config.primary_language
            ),
            value=humanize.precisedelta(
                LOADED_AT - datetime.datetime.now(tz=datetime.timezone.utc)
            ),
            inline=True,
        )
        embed.add_field(
            name=localisations.get_localized_string(
                "commands.stats.responses.hikari", user_config.primary_language
            ),
            value=hikari.__version__,
            inline=True,
        )
        embed.add_field(
            name=localisations.get_localized_string(
                "commands.stats.responses.python", user_config.primary_language
            ),
            value=python_version,
            inline=True,
        )
        embed.add_field(
            name=localisations.get_localized_string(
                "commands.stats.responses.version", user_config.primary_language
            ),
            value=VERSION,
            inline=True,
        )
        embed.set_footer(
            text=localisations.get_localized_string(
                "commands.stats.responses.cluster",
                user_config.primary_language,
                extras={"CLUSTER": CLUSTER_ID, "SHARD": shard_id},
            )
        )

        await ctx.respond(embed=embed)
        return None
