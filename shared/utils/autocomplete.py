from typing import Literal

from redis.commands.search.suggestion import Suggestion

from web.constants import REDIS_CLIENT


async def delete_autocomplete_cache():
    """Deletes the autocomplete cache"""
    await REDIS_CLIENT.delete("ac:*")


async def cache_sid_in_autocomplete(
    *,
    guild_id: int,
    suggestion_id: str,
    index: Literal[
        "shared_sid_autocomplete_index",
        "queue_sid_autocomplete_index",
        "suggestion_sid_autocomplete_index",
    ],
):
    await REDIS_CLIENT.ft(index).sugadd(
        f"ac:{guild_id}:{index}", Suggestion(string=suggestion_id)
    )


async def get_sid_autocomplete_for_guild(
    *,
    guild_id: int,
    search: str,
    index: Literal[
        "shared_sid_autocomplete_index",
        "queue_sid_autocomplete_index",
        "suggestion_sid_autocomplete_index",
    ],
    max_return: int = 20,
) -> list[str]:
    results = await REDIS_CLIENT.ft(index).sugget(
        f"ac:{guild_id}:{index}", search, num=max_return
    )
    return [r.string for r in results]
