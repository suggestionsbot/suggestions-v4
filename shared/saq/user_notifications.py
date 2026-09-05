import inspect
import logging
import time

import hikari

from bot.constants import LOCALISATIONS
from bot.utils import cv2, HandleClientHTTPResponse
from bot.utils.users import fetch_user_dm_channel_id
from shared.saq.worker import SAQ_QUEUE
from shared.tables import (
    Suggestions,
    QueuedSuggestions,
    SuggestionVotes,
    PremiumUserConfigs,
)
from shared.utils import configs
from web import constants
from bot import constants as b_constants
from web.tables import UserTokens
from web.util.table_mixins import utc_now

logger = logging.getLogger(__name__)


async def queued_suggestion_resolved_notifications(_, suggestion_id: str, guild_id: int):
    """Notifies users of when there queued suggestion has been resolved"""
    suggestion: (
        QueuedSuggestions | None
    ) = await QueuedSuggestions.fetch_queued_suggestion(suggestion_id, guild_id)
    if not suggestion:
        logger.error(
            "Queued Suggestion was none when notifying user of resolution",
            extra={"suggestion.id": suggestion_id, "suggestion.type": "queued"},
        )
        return

    user_config = await configs.ensure_user_config(suggestion.author_id)
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        try:
            dm_channel = await fetch_user_dm_channel_id(user_config.user_id, rest=client)
            (
                message_components,
                suggestion_components,
            ) = await cv2.build_queued_user_resolution_notification(
                user_config=user_config, suggestion=suggestion, rest=client
            )
            async with HandleClientHTTPResponse(
                inspect.currentframe().f_code.co_name,  # ty:ignore[unresolved-attribute],
                f"queued_suggestion_id={suggestion.id}",
            ):
                await client.create_message(dm_channel, components=message_components)
                if suggestion_components is not None:
                    await client.create_message(
                        dm_channel, components=suggestion_components
                    )

        except hikari.ForbiddenError:
            # I'd consider it 'fine' if the bot can't send this message
            logger.debug(
                "Failed to dm user about a queued suggestion resolution",
                extra={
                    "interaction.user.id": suggestion.author_id,
                    "interaction.guild.id": suggestion.guild_id,
                    "suggestion.id": suggestion_id,
                    "suggestion.type": "queued",
                },
            )


async def get_voters_for_suggestion_with_notifications_enabled(
    suggestion: Suggestions,
) -> list[SuggestionVotes]:
    premium_user_ids = await PremiumUserConfigs.select(
        PremiumUserConfigs.user_config.user_id
    ).where(PremiumUserConfigs.wants_voting_notifications.eq(value=True))
    if not premium_user_ids:
        logger.debug("No premium user configs found, returning empty list")
        return []

    valid_token_user_ids = None
    if not b_constants.ENABLE_FREE_USER_PREMIUM:
        valid_token_user_ids = await UserTokens.select(UserTokens.user_id).where(
            UserTokens.expires_at > utc_now()
        )
        if not valid_token_user_ids:
            logger.debug("No premium users found, returning empty list")
            return []

        valid_token_user_ids = [token["user_id"] for token in valid_token_user_ids]

    premium_user_ids = [user["user_config.user_id"] for user in premium_user_ids]

    query = SuggestionVotes.objects().where(
        SuggestionVotes.suggestion == suggestion,
        SuggestionVotes.user_id.is_in(premium_user_ids),
    )
    if valid_token_user_ids is not None:
        query = query.where(SuggestionVotes.user_id.is_in(valid_token_user_ids))

    return await query


async def notify_voters_of_suggestion_resolution(
    _, suggestion_id: str, guild_id: int
) -> None:
    """Notifies premium users who have subscribed to DM's of outcomes."""
    suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
        suggestion_id, guild_id
    )
    if not suggestion:
        logger.error(
            "Suggestion was none when notifying premium users of resolution",
            extra={"suggestion.id": suggestion_id},
        )
        return

    users_who_voted = await get_voters_for_suggestion_with_notifications_enabled(
        suggestion
    )
    with b_constants.OTEL_TRACER.start_as_current_span("edit_suggestion_message") as span:
        span.set_attribute("suggestion.id", suggestion_id)
        span.set_attribute("interaction.guild.id", guild_id)
        async with constants.DISCORD_REST_CLIENT.acquire(
            constants.BOT_TOKEN, hikari.TokenType.BOT
        ) as client:
            for vote in users_who_voted:
                if vote.user_id == suggestion.user_configuration.user_id:
                    # Don't notify the author of their own suggestion
                    continue

                try:
                    user_config = await configs.ensure_user_config(suggestion.author_id)
                    dm_channel = await fetch_user_dm_channel_id(vote.user_id, rest=client)
                    message_components = (
                        await cv2.build_user_resolution_voter_notification(
                            user_config=user_config, suggestion=suggestion, vote=vote
                        )
                    )
                    async with HandleClientHTTPResponse(
                        inspect.currentframe().f_code.co_name,  # ty:ignore[unresolved-attribute],
                        f"suggestion_id={suggestion.id}",
                    ):
                        await client.create_message(
                            dm_channel, components=message_components
                        )

                except hikari.ForbiddenError:
                    # I'd consider it 'fine' if the bot can't send this message
                    logger.debug(
                        "Failed to dm user about a suggestion resolution",
                        extra={
                            "interaction.user.id": suggestion.author_id,
                            "interaction.guild.id": suggestion.guild_id,
                            "suggestion.id": suggestion_id,
                        },
                    )


async def suggestion_resolved_notifications(_, suggestion_id: str, guild_id: int) -> None:
    """Notifies users of when there suggestion has been resolved"""
    # TODO Support dm'ing subscribed users
    suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
        suggestion_id, guild_id
    )
    if not suggestion:
        logger.error(
            "Suggestion was none when notifying user of resolution",
            extra={"suggestion.id": suggestion_id},
        )
        return

    await SAQ_QUEUE.enqueue(
        "notify_voters_of_suggestion_resolution",
        suggestion_id=suggestion_id,
        guild_id=guild_id,
        scheduled=time.time() + 5,
    )

    guild_config = await configs.ensure_guild_config(guild_id)
    user_config = await configs.ensure_user_config(suggestion.author_id)
    if (
        guild_config.generic_dm_messages_disabled
        or user_config.generic_dm_messages_disabled
    ):
        return

    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        try:
            dm_channel = await fetch_user_dm_channel_id(user_config.user_id, rest=client)
            message_components = await cv2.build_user_resolution_notification(
                user_config=user_config, suggestion=suggestion
            )
            async with HandleClientHTTPResponse(
                inspect.currentframe().f_code.co_name,  # ty:ignore[unresolved-attribute],
                f"suggestion_id={suggestion.id}",
            ):
                await client.create_message(dm_channel, components=message_components)

        except (hikari.ForbiddenError,):
            # I'd consider it 'fine' if the bot can't send this message
            logger.debug(
                "Failed to dm user about a suggestion resolution",
                extra={
                    "interaction.user.id": suggestion.author_id,
                    "interaction.guild.id": suggestion.guild_id,
                    "suggestion.id": suggestion_id,
                },
            )


async def notify_users_of_new_suggestion(_, suggestion_id: str, guild_id: int):
    """Notify suggestion author of creation"""
    # TODO Notify premium users who subscribed to new suggestion notifications
    suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
        suggestion_id, guild_id
    )
    if not suggestion:
        logger.error(
            "Suggestion was none when notifying user of creation",
            extra={"suggestion.id": suggestion_id},
        )
        return

    guild_config = await configs.ensure_guild_config(guild_id)
    user_config = await configs.ensure_user_config(suggestion.author_id)
    if (
        guild_config.generic_dm_messages_disabled
        or user_config.generic_dm_messages_disabled
    ):
        return

    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        try:
            dm_channel = await fetch_user_dm_channel_id(user_config.user_id, rest=client)
            components = await cv2.build_new_suggestion_notification(
                user_config=user_config, suggestion=suggestion
            )
            suggestion_components = await suggestion.as_components(
                rest=client,
                locale=user_config.primary_language,
                localisations=LOCALISATIONS,
                exclude_buttons=True,
                exclude_votes=True,
            )
            async with HandleClientHTTPResponse(
                inspect.currentframe().f_code.co_name,  # ty:ignore[unresolved-attribute],
                f"suggestion_id={suggestion.id}",
            ):
                await client.create_message(dm_channel, components=components)
                await client.create_message(dm_channel, components=suggestion_components)
        except hikari.ForbiddenError:
            # I'd consider it 'fine' if the bot can't send this message
            logger.debug(
                "Failed to dm user about a suggestion",
                extra={
                    "interaction.user.id": suggestion.author_id,
                    "interaction.guild.id": suggestion.guild_id,
                    "suggestion.id": suggestion_id,
                },
            )
