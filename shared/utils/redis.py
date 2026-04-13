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
