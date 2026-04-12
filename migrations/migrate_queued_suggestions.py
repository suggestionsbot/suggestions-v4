import asyncio
import time
from typing import cast

from alaric import Document
from motor.motor_asyncio import AsyncIOMotorClient
from tqdm.asyncio import tqdm

from bot.utils import generate_id
from migrations.objects import QueuedSuggestion
from shared.tables import QueuedSuggestions, QueuedSuggestionStateEnum

__mongo = AsyncIOMotorClient("mongodb://localhost:27017")
db = __mongo["suggestions"]
small = ""
queued_suggestions: Document = Document(
    db,
    f"queued_suggestions{small}",
    converter=QueuedSuggestion,
)
queued_suggestions_count: int = 0


async def get_ids_from_queued():
    global queued_suggestions_count
    queued_suggestions_count = await queued_suggestions.count({})


async def build_initial_objects(pbar):
    to_insert: list[QueuedSuggestions] = []
    async for qs in queued_suggestions.create_cursor():
        qs = cast(QueuedSuggestion, qs)
        assert qs.guild_config_id is not None
        assert qs.user_config_id is not None
        to_insert.append(
            QueuedSuggestions(
                guild_configuration=qs.guild_config_id,
                user_configuration=qs.user_config_id,
                author_display_name=(
                    f"<@{qs.suggestion_author_id}>"
                    if not qs.is_anonymous
                    else "Anonymous"
                ),
                sID=(qs._id if isinstance(qs._id, str) else generate_id()),
                state_raw=(
                    QueuedSuggestionStateEnum.PENDING
                    if qs.still_in_queue
                    else (
                        QueuedSuggestionStateEnum.APPROVED
                        if qs.related_suggestion_id is not None
                        else QueuedSuggestionStateEnum.REJECTED
                    )
                ),
                suggestion=qs.suggestion,
                channel_id=qs.channel_id,
                message_id=qs.message_id,
                resolved_by=qs.resolved_by,
                resolved_by_display_text=(
                    None
                    if qs.still_in_queue
                    else f"<@{qs.resolved_by}>" if not qs.is_anonymous else "Anonymous"
                ),
                resolved_note=qs.resolution_note,
                resolved_at=qs.resolved_at,
                image_urls=[qs.image_url] if qs.image_url else [],
                related_suggestion_id=qs.related_suggestion_id,
            )
        )

        if len(to_insert) == 1000:
            await QueuedSuggestions.insert(*to_insert).on_conflict(action="DO NOTHING")
            to_insert = []
            pbar.update(1000)

    await QueuedSuggestions.insert(*to_insert).on_conflict(action="DO NOTHING")
    pbar.update(len(to_insert))


async def main():
    start_time = time.time()
    await get_ids_from_queued()
    print(f"{queued_suggestions_count} queued suggestions found")

    pbar = tqdm(total=queued_suggestions_count)
    import asyncio

    async with asyncio.TaskGroup() as tg:
        tg.create_task(build_initial_objects(pbar))

    pbar.close()
    print("--- %s seconds to complete ---" % (round(time.time() - start_time, 5)))


if __name__ == "__main__":
    asyncio.run(main())
