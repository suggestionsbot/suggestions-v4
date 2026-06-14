import hikari
from datetime import timedelta


async def get_accurate_guild_count() -> int:
    """Returns a count of how many guilds are present.

    Notes
    -----
    While this doesn't block Redis, it takes
    awhile to return results. 15-45 seconds it seems.
    """
    from web.constants import REDIS_CLIENT

    total_guilds: int = 0
    async for _ in REDIS_CLIENT.scan_iter("bot:guilds:is_in:*", count=1000):
        total_guilds += 1

    return total_guilds


async def cache_guild_queue_info(guild: hikari.Guild | hikari.RESTGuild) -> dict:
    from web.constants import REDIS_CLIENT

    icon = guild.make_icon_url()
    if icon is not None:
        icon = icon.url

    data = {
        "name": guild.name,
        "icon": icon,
    }

    await REDIS_CLIENT.hsetex(
        f"guild_queue:{guild.id}",
        mapping=data,
        ex=timedelta(minutes=15),
    )  # ty:ignore[no-matching-overload]
    return data


async def get_guild_queue_info(guild_id: int) -> dict | None:
    from web.constants import REDIS_CLIENT

    return await REDIS_CLIENT.hgetall(f"guild_queue:{guild_id}")
