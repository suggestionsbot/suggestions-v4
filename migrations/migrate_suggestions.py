import asyncio
import json
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

__mongo = AsyncIOMotorClient("mongodb://localhost:27017")
db = __mongo["suggestions"]
small = ""
suggestions: Document = Document(
    db,
    f"suggestions{small}",
    converter=Suggestion,
)
suggestions_count: int = 0
votes: int = 0


async def get_ids_from_queued():
    global suggestions_count
    suggestions_count = await suggestions.count({})


async def get_ids_from_suggestions():
    global votes
    async for s in suggestions.create_cursor():
        s = cast(Suggestion, s)
        votes += len(s.up_voted_by)
        votes += len(s.down_voted_by)


async def build_initial_objects(pbar):
    i = 0
    to_insert: list[Suggestions] = []
    async for s in suggestions.create_cursor():
        s = cast(Suggestion, s)
        assert s.guild_config_id is not None
        assert s.user_config_id is not None

        if not s.uses_views_for_votes:
            # We no longer support reaction voting
            # None left anywho
            continue

        if s.anonymous_resolution is None:
            # Make non-anonymous by default
            s.anonymous_resolution = False

        i += 1
        to_insert.append(
            Suggestions(
                guild_configuration=s.guild_config_id,
                user_configuration=s.user_config_id,
                author_display_name=(
                    f"<@{s.suggestion_author_id}>" if not s.is_anonymous else "Anonymous"
                ),
                sID=(s._id if isinstance(s._id, str) else generate_id()),
                state_raw=(
                    SuggestionStateEnum.PENDING
                    if s.state == SuggestionState.pending
                    else (
                        SuggestionStateEnum.APPROVED
                        if s.state == SuggestionState.approved
                        else (
                            SuggestionStateEnum.REJECTED
                            if s.state == SuggestionState.rejected
                            else SuggestionStateEnum.CLEARED
                        )
                    )
                ),
                suggestion=s.suggestion.replace("\x00", ""),
                channel_id=s.channel_id,
                message_id=s.message_id,
                resolved_by=s.resolved_by,
                resolved_by_display_text=(
                    None
                    if s.resolved_by is None
                    else (
                        f"<@{s.resolved_by}>"
                        if not s.anonymous_resolution
                        else "Anonymous"
                    )
                ),
                resolved_note=s.resolution_note,
                resolved_at=s.resolved_at,
                image_urls=[s.image_url] if s.image_url else [],
                moderator_note=s.note,
                moderator_note_added_by=s.note_added_by,
                moderator_note_added_by_display_text=(
                    None
                    if s.note_added_by is None
                    else (
                        f"<@{s.note_added_by}>"
                        if not s.anonymous_resolution
                        else "Anonymous"
                    )
                ),
                thread_id=s.thread_id,
            )
        )

        UPDATE_COUNT = 1000
        if len(to_insert) == UPDATE_COUNT:
            # if i >= 143000:
            #     s = [s for s in to_insert]
            #     d = [s.suggestion for s in to_insert]
            #     for row in batched(s, 100):
            #         try:
            #             await Suggestions.insert(*row).on_conflict(action="DO NOTHING")
            #         except Exception as e:
            #             for item in row:
            #                 try:
            #                     await Suggestions.insert(item).on_conflict(
            #                         action="DO NOTHING"
            #                     )
            #                 except Exception as e:
            #                     print(repr(item))
            #                     print()
            #                     print()
            #
            #         pbar.update(len(row))
            #     # print(to_insert)
            #     to_insert = []
            # else:
            await Suggestions.insert(*to_insert).on_conflict(action="DO NOTHING")
            to_insert = []
            pbar.update(UPDATE_COUNT)

    if to_insert:
        await Suggestions.insert(*to_insert).on_conflict(action="DO NOTHING")
        pbar.update(len(to_insert))


async def build_votes(pbar):
    to_insert: list[SuggestionVotes] = []
    async for s in suggestions.create_cursor():
        s = cast(Suggestion, s)
        assert s.guild_config_id is not None
        assert s.user_config_id is not None
        if not s.uses_views_for_votes:
            # We no longer support reaction voting
            # None left anywho
            continue

        postgres_s = await Suggestions.objects().get(Suggestions.sID == s._id)

        for up_vote_id in s.up_voted_by:
            to_insert.append(
                SuggestionVotes(
                    suggestion=postgres_s,
                    user_id=up_vote_id,
                    vote_type=SuggestionsVoteTypeEnum.UpVote,
                )
            )

        for down_vote_id in s.down_voted_by:
            to_insert.append(
                SuggestionVotes(
                    suggestion=postgres_s,
                    user_id=down_vote_id,
                    vote_type=SuggestionsVoteTypeEnum.DownVote,
                )
            )

        if to_insert:
            await SuggestionVotes.insert(*to_insert).on_conflict(action="DO NOTHING")
            to_insert = []
            pbar.update(len(to_insert))

    if to_insert:
        await SuggestionVotes.insert(*to_insert).on_conflict(action="DO NOTHING")
        pbar.update(len(to_insert))


async def main():
    start_time = time.time()
    await get_ids_from_queued()
    await get_ids_from_suggestions()
    print(f"{intcomma(suggestions_count)} suggestions found")
    print(f"{intcomma(votes)} votes found")
    await asyncio.sleep(1)

    pbar = tqdm(total=suggestions_count)
    await build_initial_objects(pbar)
    pbar.close()
    print(f"Inserted all suggestions")
    await asyncio.sleep(1)

    pbar = tqdm(total=votes)
    await build_votes(pbar)
    pbar.close()
    print("--- %s seconds to complete ---" % (round(time.time() - start_time, 5)))


if __name__ == "__main__":
    asyncio.run(main())
