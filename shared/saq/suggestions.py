from typing import cast

from shared.saq.worker import SAQ_QUEUE, SAQ_TIMEOUT
import contextlib
import logging
import time
from datetime import timedelta

import commons
import hikari

from bot import constants as b_constants
from shared import utils
from shared.utils import query_helpers
from shared.tables import (
    Suggestions,
    QueuedSuggestions,
    SuggestionStateEnum,
    QueuedSuggestionStateEnum,
)
from shared.utils.configs import ensure_guild_config
from web import constants
from web.constants import REDIS_CLIENT

log = logging.getLogger(__name__)


async def queue_suggestion_edit(
    suggestion_id: str,
    guild_id: int,
    exclude_buttons: bool = False,
    as_resolved: bool = False,
) -> None:
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
        exclude_buttons=exclude_buttons,
        as_resolved=as_resolved,
        scheduled=time.time() + 10,
        timeout=SAQ_TIMEOUT,
    )


async def edit_suggestion_message(
    ctx,
    suggestion_id: str,
    guild_id: int,
    exclude_buttons: bool,
    as_resolved: bool,
) -> None:
    suggestion = await Suggestions.fetch_suggestion(suggestion_id, guild_id)
    if suggestion is None:
        log.error(
            "Suggestion was none when attempting to edit",
            extra={"suggestion.id": suggestion_id},
        )
        return

    if suggestion.channel_id is None or suggestion.message_id is None:
        log.error(
            "Suggestion channel or message id was none when attempting to edit",
            extra={
                "suggestion.id": suggestion_id,
                "suggestion.channel.id": suggestion.channel_id,
                "suggestion.message.id": suggestion.message_id,
            },
        )
        return

    log.debug(
        "SAQ edit_suggestion_message for %s has timeout %s",
        suggestion_id,
        ctx["job"].timeout,
    )
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        await ctx["job"].update()
        guild_config = await ensure_guild_config(suggestion.guild_id)
        components = await suggestion.as_components(
            guild_config=guild_config,
            locale=guild_config.primary_language,
            rest=client,
            localisations=b_constants.LOCALISATIONS,
            exclude_buttons=exclude_buttons,
            as_resolved=as_resolved,
        )

        try:
            await client.edit_message(
                suggestion.channel_id,
                suggestion.message_id,
                components=components,
                # This must be set to None to clear old embeds
                # to ensure we remain backwards compatible
                embeds=None,
            )
        except hikari.NotFoundError:
            log.error(
                "Suggestion was not found when attempting to edit",
                extra={"suggestion.id": suggestion_id},
            )
        except hikari.ForbiddenError as e:
            log.error(
                "Encountered ForbiddenError when attempting to edit suggestion",
                extra={
                    "suggestion.id": suggestion_id,
                    "traceback": commons.exception_as_string(e),
                },
            )
            await SAQ_QUEUE.enqueue(
                "notify_guild_of_missing_suggestion_permissions",
                guild_id=guild_config.guild_id,
            )


async def populate_sid_autocomplete(ctx):
    """Populates autocomplete of all queued and regular suggestion sids when called.

    We shouldn't need to do this often given they add themselves but it
    will help ensure the consistency of data if I miss something
    """
    await utils.delete_autocomplete_cache(ctx["job"])
    for table in [Suggestions, QueuedSuggestions]:
        async for row in query_helpers.iterate_over_table(
            table,
            [table.guild_configuration],
        ):
            # Won't duplicate entries if already present :)
            if isinstance(row, Suggestions):
                if row.state == SuggestionStateEnum.CLEARED:
                    # Dont add cleared suggestions to autocomplete
                    continue

                await utils.cache_sid_in_autocomplete(
                    guild_id=row.guild_configuration.guild_id,
                    suggestion_id=row.sID,
                    index="suggestion_sid_autocomplete_index",
                )
                await utils.cache_sid_in_autocomplete(
                    guild_id=row.guild_configuration.guild_id,
                    suggestion_id=row.sID,
                    index="shared_sid_autocomplete_index",
                )
            else:
                if row.state == QueuedSuggestionStateEnum.CLEARED:
                    # Dont add cleared suggestions to autocomplete
                    continue

                await utils.cache_sid_in_autocomplete(
                    guild_id=row.guild_configuration.guild_id,
                    suggestion_id=row.sID,
                    index="queue_sid_autocomplete_index",
                )
                await utils.cache_sid_in_autocomplete(
                    guild_id=row.guild_configuration.guild_id,
                    suggestion_id=row.sID,
                    index="shared_sid_autocomplete_index",
                )


async def test_message_send(_):
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        await client.create_message(1459693890662830102, "SAQ works as expected")
