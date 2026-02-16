import asyncio
import logging
import time
from datetime import timedelta
from unittest.mock import MagicMock

import hikari
import lightbulb

from shared.tables import Suggestions
from shared.utils.configs import ensure_guild_config
from web import constants
from bot import constants as b_constants
from web.constants import REDIS_CLIENT

log = logging.getLogger(__name__)


async def queue_suggestion_edit(_, suggestion_id: str) -> None:
    redis_key = f"saq:queue_suggestion_edit:{suggestion_id}"
    result = await REDIS_CLIENT.set(
        redis_key, suggestion_id, nx=True, ex=timedelta(seconds=9)
    )
    if result is None:
        # There is already a queued edit
        return

    from shared.saq.worker import SAQ_QUEUE

    await SAQ_QUEUE.enqueue(
        "edit_suggestion_message",
        suggestion_id=suggestion_id,
        scheduled=time.time() + 10,
    )


async def edit_suggestion_message(_, suggestion_id: str) -> None:
    suggestion = await Suggestions.fetch_suggestion(suggestion_id)
    if suggestion is None:
        log.error(
            "Suggestion was none when attempting to edit",
            extra={"suggestion.id": suggestion_id},
        )

    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        fake_ctx: lightbulb.Context = MagicMock(spec=lightbulb.Context)
        fake_ctx.user.id = suggestion.author_id  # noqa
        fake_ctx.guild_id = suggestion.guild_id  # noqa
        fake_ctx.channel_id = suggestion.channel_id  # noqa
        guild_config = await ensure_guild_config(suggestion.guild_id)
        components = await suggestion.as_components(
            use_guild_locale=True,
            guild_config=guild_config,
            ctx=fake_ctx,
            rest=client,
            localisations=b_constants.LOCALISATIONS,
        )
        await client.edit_message(
            suggestion.channel_id, suggestion.message_id, components=components
        )


async def test_message_send(_):
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        await client.create_message(1459693890662830102, "SAQ works as expected")
