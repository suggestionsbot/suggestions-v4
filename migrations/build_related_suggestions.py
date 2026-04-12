import asyncio
import time

import orjson
from motor.motor_asyncio import AsyncIOMotorClient
from tqdm.asyncio import tqdm

from bot import bot

from shared.tables import (
    QueuedSuggestions,
)

__mongo = AsyncIOMotorClient("mongodb://localhost:27017")
db = __mongo["suggestions"]
small = ""


async def build_related_suggestions():
    pgs = {}
    with open("migrations/suggestions.json", "r") as f:
        raw_data = orjson.loads(f.read())
        for row in raw_data:
            pgs[row["sID"]] = row["id"]

    total = await QueuedSuggestions.count().where(
        QueuedSuggestions.related_suggestion_id.is_not_null()
    )
    failed = 0
    pbar = tqdm(total=total, bar_format="{l_bar}{bar:25}{r_bar}{bar:-10b}")
    for qs in await QueuedSuggestions.objects().where(
        QueuedSuggestions.related_suggestion_id.is_not_null()
    ):
        if qs.related_suggestion_id in pgs:
            qs.related_suggestion = pgs[qs.related_suggestion_id]
            await qs.save()
        else:
            failed += 1
        pbar.update(1)

    pbar.close()
    print(f"{total} total, {failed} failed to lookup")


async def main():
    start_time = time.time()
    await build_related_suggestions()
    print("--- %s seconds to complete ---" % (round(time.time() - start_time, 5)))


if __name__ == "__main__":
    asyncio.run(main())
