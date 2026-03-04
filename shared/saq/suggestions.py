import logging
import time
from datetime import timedelta
from unittest.mock import MagicMock

import hikari
import lightbulb

from bot import constants as b_constants
from shared import utils
from shared.tables import Suggestions, QueuedSuggestions
from shared.utils.configs import ensure_guild_config
from web import constants
from web.constants import REDIS_CLIENT

log = logging.getLogger(__name__)


async def queue_suggestion_edit(suggestion_id: str, guild_id: int) -> None:
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
        guild_id=guild_id,
        scheduled=time.time() + 10,
    )


async def edit_suggestion_message(_, suggestion_id: str, guild_id: int) -> None:
    suggestion = await Suggestions.fetch_suggestion(suggestion_id, guild_id)
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


async def populate_sid_autocomplete(_):
    """Populates autocomplete of all queued and regular suggestion sids when called

    We shouldn't need to do this often given they add themselves but it
    will help ensure the consistency of data if I miss something
    """
    page_size = 500

    async def build_base_query(
        *,
        table_class,
        prefetch_cols,
        order_by,
        cursor_col,
        next_cursor_id: str | None,
    ):
        base_query = (
            table_class.objects(*prefetch_cols).limit(page_size + 1).order_by(order_by)
        )
        if next_cursor_id is not None:
            base_query = base_query.where(cursor_col >= next_cursor_id)

        return base_query

    for table in [Suggestions, QueuedSuggestions]:
        next_cursor = None
        has_next_queued: bool = True
        while has_next_queued:
            query = await build_base_query(
                table_class=table,
                prefetch_cols=[table.guild_configuration],
                order_by=table.id,
                cursor_col=table.id,
                next_cursor_id=next_cursor,
            )

            rows: list = await query.run()
            next_cursor = None
            if len(rows) > page_size:
                final_row = rows.pop(-1)
                next_cursor = final_row.id
            else:
                has_next_queued = False

            for row in rows:
                # Won't duplicate entries if already present :)
                await utils.cache_sid_in_autocomplete(
                    guild_id=row.guild_configuration.guild_id,
                    suggestion_id=row.sID,
                    index="shared_sid_autocomplete_index",
                )
                if isinstance(row, Suggestions):
                    await utils.cache_sid_in_autocomplete(
                        guild_id=row.guild_configuration.guild_id,
                        suggestion_id=row.sID,
                        index="suggestion_sid_autocomplete_index",
                    )
                else:
                    await utils.cache_sid_in_autocomplete(
                        guild_id=row.guild_configuration.guild_id,
                        suggestion_id=row.sID,
                        index="queue_sid_autocomplete_index",
                    )


async def test_message_send(_):
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        await client.create_message(1459693890662830102, "SAQ works as expected")
