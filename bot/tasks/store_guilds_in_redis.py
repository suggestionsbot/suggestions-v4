import datetime
import logging

import hikari
import lightbulb
import orjson

from bot.constants import CLUSTER_ID
from web import constants

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


# This is set to 15 minutes to handle
# bot restarts and the fact thats about how
# long it takes to get the bot running and repopulate redis
#
# We also don't mind if edits occur in a short period
# after the bot leaves as thats basically a noop
time_to_cache = datetime.timedelta(minutes=15)


@loader.task(lightbulb.uniformtrigger(minutes=15, wait_first=False))
async def update_redis(bot: hikari.GatewayBot) -> None:
    """Updates redis with bot specific info such as guilds"""
    guilds = bot.cache.get_guilds_view()
    guild_count = len(guilds.keys())
    for guild_id in guilds.keys():
        await constants.REDIS_CLIENT.set(
            f"bot:guilds:is_in:{guild_id}",
            orjson.dumps(guild_id),
            ex=int(time_to_cache.total_seconds()),
        )

    logger.info(
        "Updated redis with current guilds for cluster %s",
        CLUSTER_ID,
        extra={"cluster.id": CLUSTER_ID, "cluster.guilds.count": guild_count},
    )
