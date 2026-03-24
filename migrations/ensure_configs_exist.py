import asyncio
import time
from itertools import batched
from typing import cast

import orjson
from alaric import Document, AQ
from alaric.comparison import EQ
from motor.motor_asyncio import AsyncIOMotorClient
from piccolo.columns.combination import WhereRaw
from pymongo import UpdateMany
from tqdm.asyncio import tqdm

from bot import bot  # noqa # Import this first and it fixes circular imports
from migrations.objects import QueuedSuggestion, Suggestion
from shared.tables import PremiumGuildConfigs, GuildConfigs, UserConfigs

all_user_ids: set[int] = set()
all_guild_ids: set[int] = set()
users_created: int = 0
guilds_created: int = 0
__mongo = AsyncIOMotorClient("mongodb://localhost:27017")
db = __mongo["suggestions"]
small = ""
suggestions: Document = Document(
    db,
    f"suggestions{small}",
    converter=Suggestion,
)
queued_suggestions: Document = Document(
    db,
    f"queued_suggestions{small}",
    converter=QueuedSuggestion,
)


async def get_ids_from_queued():
    async for qs in queued_suggestions.create_cursor():
        qs = cast(QueuedSuggestion, qs)
        all_user_ids.add(qs.suggestion_author_id)
        all_user_ids.add(qs.resolved_by)
        all_guild_ids.add(qs.guild_id)


async def get_ids_from_suggestions():
    async for s in suggestions.create_cursor():
        s = cast(Suggestion, s)
        all_user_ids.add(s.suggestion_author_id)
        all_user_ids.add(s.resolved_by)
        all_user_ids.add(s.note_added_by)
        all_guild_ids.add(s.guild_id)


async def fix_guild_configs():
    """Fixes blocked_users_json"""
    to_update = (
        await GuildConfigs.objects()
        .where(GuildConfigs.blocked_users_json.is_not_null())
        .where(WhereRaw("blocked_users_json::text != '[]'"))
    )
    for gc in to_update:
        gc.blocked_users = orjson.loads(gc.blocked_users_json)
        await gc.save()


async def create_users(pbar):
    for user_ids in batched(all_user_ids, 1000):
        to_insert = [
            UserConfigs(user_id=user_id) for user_id in user_ids if user_id is not None
        ]
        await UserConfigs.insert(*to_insert).on_conflict(action="DO NOTHING")

        fresh_inserts = await UserConfigs.objects().where(
            UserConfigs.user_id.is_in(user_ids)
        )

        operations = []
        for uc in fresh_inserts:
            operations.append(
                UpdateMany(
                    {"suggestion_author_id": {"$eq": uc.user_id}},
                    {"$set": {"user_config_id": uc.id}},
                )
            )

        await suggestions.raw_collection.bulk_write(operations, ordered=False)
        await queued_suggestions.raw_collection.bulk_write(operations, ordered=False)
        pbar.update(1000)


async def create_guilds(pbar):
    for guild_ids in batched(all_guild_ids, 1000):
        pgc_cache: dict[int, PremiumGuildConfigs | int] = {}
        for guild_id in guild_ids:
            if guild_id is not None:
                pgc_cache[guild_id] = PremiumGuildConfigs(guild_id=guild_id)

        await PremiumGuildConfigs.insert(*pgc_cache.values()).on_conflict(
            action="DO NOTHING"
        )

        for item in await PremiumGuildConfigs.objects().where(
            PremiumGuildConfigs.guild_id.is_in(guild_ids)
        ):
            pgc_cache[item.guild_id] = item

        to_insert = [
            GuildConfigs(guild_id=guild_id, premium=pgc_cache[guild_id])
            for guild_id in guild_ids
            if guild_id is not None
        ]
        await GuildConfigs.insert(*to_insert).on_conflict(action="DO NOTHING")

        fresh_inserts = await GuildConfigs.objects().where(
            GuildConfigs.guild_id.is_in(guild_ids)
        )

        operations = []
        for gc in fresh_inserts:
            operations.append(
                UpdateMany(
                    {"guild_id": {"$eq": gc.guild_id}},
                    {"$set": {"guild_config_id": gc.id}},
                )
            )

        await suggestions.raw_collection.bulk_write(operations, ordered=False)
        await queued_suggestions.raw_collection.bulk_write(operations, ordered=False)
        pbar.update(1000)


async def main():
    start_time = time.time()
    await get_ids_from_queued()
    await get_ids_from_suggestions()
    print(f"{len(all_user_ids)} users found")
    print(f"{len(all_guild_ids)} guilds found")

    pbar = tqdm(total=len(all_guild_ids) + len(all_user_ids))
    async with asyncio.TaskGroup() as tg:
        tg.create_task(create_users(pbar))
        tg.create_task(create_guilds(pbar))

    pbar.close()
    await fix_guild_configs()
    print("--- %s seconds to complete ---" % (round(time.time() - start_time, 5)))


if __name__ == "__main__":
    asyncio.run(main())
