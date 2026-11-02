import asyncio
from opentelemetry import trace

from shared.saq.worker import SAQ_QUEUE, traced_task, enqueue_traced
import logging
import time
from datetime import timedelta

import commons
import hikari
from saq.types import Context

from bot import constants as b_constants
from shared import utils
from shared.utils import query_helpers, configs
from shared.tables import (
    Suggestions,
    QueuedSuggestions,
    SuggestionStateEnum,
    QueuedSuggestionStateEnum,
    SuggestionButtons,
)
from shared.utils.configs import ensure_guild_config
from web import constants

log = logging.getLogger(__name__)


async def queue_suggestion_edit(
    suggestion_id: str,
    guild_id: int,
    exclude_buttons: bool = False,
    as_resolved: bool = False,
) -> None:
    redis_key = f"saq:queue_suggestion_edit:{suggestion_id}"
    result = await constants.REDIS_CLIENT.set(
        redis_key, suggestion_id, nx=True, ex=timedelta(seconds=9)
    )
    if result is None:
        # There is already a queued edit
        return

    await enqueue_traced(
        SAQ_QUEUE,
        "edit_suggestion_message",
        suggestion_id=suggestion_id,
        guild_id=guild_id,
        exclude_buttons=exclude_buttons,
        as_resolved=as_resolved,
        scheduled=time.time() + 10,
    )


async def queue_sticky_button_edit(
    channel_id: int,
    guild_id: int,
) -> None:
    redis_key = f"saq:queue_sticky_button_edit:{channel_id}"
    result = await constants.REDIS_CLIENT.set(
        redis_key, channel_id, nx=True, ex=timedelta(seconds=9)
    )
    if result is None:
        # There is already a queued edit
        return

    await enqueue_traced(
        SAQ_QUEUE,
        "sticky_button_edit",
        channel_id=channel_id,
        guild_id=guild_id,
        scheduled=time.time() + 10,
    )


@traced_task
async def sticky_button_edit(  # noqa: C901
    ctx: Context,
    channel_id: int,
    guild_id: int,
) -> None:
    span = trace.get_current_span()
    if span.get_span_context().is_valid:
        span.set_attribute("interaction.guild.id", guild_id)

    guild_config = await configs.ensure_guild_config(guild_id)
    suggestion_buttons: list[
        SuggestionButtons
    ] = await SuggestionButtons.fetch_sticky_buttons_for_channel(
        channel_id=channel_id, guild_configuration=guild_config
    )
    if not suggestion_buttons:
        log.debug("No buttons to update")
        return

    # These are all sticky and we should therefore update something
    list_of_message_ids: set[int] = {sb.message_id for sb in suggestion_buttons}

    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        await ctx["job"].update()
        try:
            iterator = client.fetch_messages(channel_id).limit(1)
            async for message in iterator:
                if message.id in list_of_message_ids:
                    log.debug(
                        "The latest message is still a suggestion button, early return"
                    )
                    return

        except hikari.ForbiddenError:
            log.error("Missing permissions to fetch message history")
            return
        except hikari.NotFoundError:
            log.error("Couldn't find channel to lookup message in?")
            return

        # Need to edit at this point
        # Note if multiple 'sticky' messages exist then that's annoying
        # but if it's what the user wants...
        for button in suggestion_buttons:
            await asyncio.sleep(3)  # Hello rate limits
            try:
                await client.delete_message(channel_id, button.message_id)
            except hikari.ForbiddenError:
                log.error("Missing permissions to delete button message")
                return
            except hikari.NotFoundError:
                log.error("Couldn't find the button to delete, continuing")

            components = await button.build_suggestion_button(guild_config)
            try:
                message = await client.create_message(channel_id, components=components)
                button.message_id = message.id
                await button.save()
            except hikari.ForbiddenError:
                log.error("Missing permissions to send new message to channel")
                return
            except hikari.NotFoundError:
                log.error("Couldn't find channel to lookup to send?")
                return


@traced_task
async def edit_suggestion_message(
    ctx: Context,
    suggestion_id: str,
    guild_id: int,
    exclude_buttons: bool,
    as_resolved: bool,
) -> None:
    span = trace.get_current_span()
    if span.get_span_context().is_valid:
        span.set_attribute("suggestion.id", suggestion_id)
        span.set_attribute("interaction.guild.id", guild_id)

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
            await enqueue_traced(
                SAQ_QUEUE,
                "notify_guild_of_missing_suggestion_permissions",
                guild_id=guild_config.guild_id,
            )


@traced_task
async def populate_sid_autocomplete(ctx: Context) -> None:
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
