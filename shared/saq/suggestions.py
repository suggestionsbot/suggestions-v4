import logging
import time
from datetime import timedelta

from shared.saq.worker import SAQ_QUEUE
from shared.tables import Suggestions
from web.constants import REDIS_CLIENT

log = logging.getLogger(__name__)


async def queue_suggestion_edit(suggestion_id: int) -> None:
    redis_key = f"saq:queue_suggestion_edit:{suggestion_id}"
    result = await REDIS_CLIENT.set(
        redis_key, suggestion_id, nx=True, ex=timedelta(seconds=9)
    )
    if result is None:
        # There is already a queued edit
        return

    await SAQ_QUEUE.enqueue(
        "edit_suggestion_message",
        suggestion_id=suggestion_id,
        scheduled=time.time() + 10,
    )


async def edit_suggestion_message(_, suggestion_id: int) -> None:
    suggestion = await Suggestions.objects().get(Suggestions.id == suggestion_id)
    if suggestion is None:
        log.error(
            "Suggestion was none when attempting to edit",
            extra={"suggestion.id": suggestion_id},
        )

    raise ValueError("Failed to edit suggestion")
