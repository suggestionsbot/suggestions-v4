from redis.commands.search.suggestion import Suggestion

from web.constants import REDIS_CLIENT


async def cache_sid_in_autocomplete(*, guild_id: int, suggestion_id: str):
    await REDIS_CLIENT.ft("sid_autocomplete_index").sugadd(
        guild_id, Suggestion(string=suggestion_id)
    )


async def get_sid_autocomplete_for_guild(
    *, guild_id: int, search: str, max_return: int = 20
) -> list[str]:
    results = await REDIS_CLIENT.ft("sid_autocomplete_index").sugget(
        guild_id, search, num=max_return
    )
    return [r.string for r in results]
