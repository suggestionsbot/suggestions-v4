from litestar_saq import Job
from itertools import batched
from typing import Literal

from redis.commands.search.suggestion import Suggestion

from web.constants import REDIS_CLIENT


async def delete_autocomplete_cache(saq_job: Job | None = None) -> None:
    """Deletes the autocomplete cache."""
    keys_present: list[str] = []
    async for item in REDIS_CLIENT.scan_iter("ac:*", count=1000):
        keys_present.append(item)
        if saq_job is not None:
            await saq_job.update()

    for keys in batched(keys_present, n=1000):
        await REDIS_CLIENT.unlink(*keys)
        if saq_job is not None:
            await saq_job.update()


async def delete_autocomplete_cache_sid(suggestion_id: str, guild_id: int) -> None:
    """Deletes the autocomplete cache sid from all caches."""
    index = [
        "shared_sid_autocomplete_index",
        "queue_sid_autocomplete_index",
        "suggestion_sid_autocomplete_index",
    ]
    for idx in index:
        await REDIS_CLIENT.ft(idx).sugdel(
            f"ac:{guild_id}:{idx}", suggestion_id
        )  # ty:ignore[invalid-await]


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
