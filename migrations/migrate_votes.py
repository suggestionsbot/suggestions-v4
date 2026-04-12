import asyncio
import json
import os
import time
from itertools import batched
from pathlib import Path
from typing import cast

import orjson
from alaric import Document
from humanize import intcomma
from motor.motor_asyncio import AsyncIOMotorClient
from tqdm.asyncio import tqdm

from bot.utils import generate_id
from migrations.objects import Suggestion, SuggestionState
from shared.tables import (
    Suggestions,
    SuggestionStateEnum,
    SuggestionVotes,
    SuggestionsVoteTypeEnum,
)
from shared.tables.mixins.audit import utc_now

__mongo = AsyncIOMotorClient("mongodb://localhost:27017")
db = __mongo["suggestions"]
small = ""
suggestions: Document = Document(
    db,
    f"suggestions{small}",
    converter=Suggestion,
)
votes: int = 0


async def get_votes_from_suggestions():
    global votes
    async for s in suggestions.create_cursor():
        s = cast(Suggestion, s)
        votes += len(s.up_voted_by)
        votes += len(s.down_voted_by)


async def write_vote_csv():
    pgs = {}
    with open("migrations/suggestions.json", "r") as f:
        raw_data = orjson.loads(f.read())
        for row in raw_data:
            pgs[row["sID"]] = row["id"]

    created_at = last_modified_at = utc_now()
    to_write = Path("migrations/votes.csv")
    if to_write.exists():
        os.remove(to_write.absolute())

    pbar = tqdm(total=votes, bar_format="{l_bar}{bar:25}{r_bar}{bar:-10b}")
    with open(to_write, "w") as f:
        async for s in suggestions.create_cursor():
            s = cast(Suggestion, s)
            if not s.uses_views_for_votes:
                # We no longer support reaction voting
                # None left anywho
                continue

            pgs_id = pgs[s._id]
            for vote in s.up_voted_by:
                f.write(
                    f"{created_at.isoformat()},{last_modified_at.isoformat()},{pgs_id},{vote},{SuggestionsVoteTypeEnum.UpVote.value}\n"
                )
                pbar.update(1)

            for vote in s.up_voted_by:
                f.write(
                    f"{created_at.isoformat()},{last_modified_at.isoformat()},{pgs_id},{vote},{SuggestionsVoteTypeEnum.DownVote.value}\n"
                )
                pbar.update(1)


async def main():
    start_time = time.time()
    await get_votes_from_suggestions()
    print(f"{intcomma(votes)} votes found")
    await asyncio.sleep(1)

    await write_vote_csv()

    print("--- %s seconds to complete ---" % (round(time.time() - start_time, 5)))


if __name__ == "__main__":
    asyncio.run(main())
