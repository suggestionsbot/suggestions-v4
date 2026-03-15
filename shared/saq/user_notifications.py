import logging

import hikari
from stripe import LoginLink

from bot.constants import LOCALISATIONS
from bot.utils import cv2
from shared.tables import Suggestions
from shared.utils import configs
from web import constants

logger = logging.getLogger(__name__)


async def suggestion_resolved_notifications(_, suggestion_id: str, guild_id: int):
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

    user_config = await configs.ensure_user_config(suggestion.author_id)
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        try:
            dm_channel = await client.create_dm_channel(
                hikari.Snowflake(suggestion.author_id)
            )
            message_components = await cv2.build_user_resolution_notification(
                user_config=user_config, suggestion=suggestion
            )
            await dm_channel.send(components=message_components)

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
            dm_channel = await client.create_dm_channel(
                hikari.Snowflake(suggestion.author_id)
            )
            await dm_channel.send(
                LOCALISATIONS.get_localized_string(
                    "saq.notify_users_of_new_suggestion.responses.suggestion_created",
                    user_config.primary_language,
                    extras={
                        "AUTHOR": suggestion.author_display_name,
                        "CHANNEL": f"<#{suggestion.channel_id}>",
                        "SUGGESTION_LINK": suggestion.message_jump_link,
                    },
                ),
            )
            await dm_channel.send(
                components=await suggestion.as_components(
                    rest=client,
                    locale=user_config.primary_language,
                    localisations=LOCALISATIONS,
                    exclude_buttons=True,
                    exclude_votes=True,
                ),
            )
        except (hikari.ForbiddenError,):
            # I'd consider it 'fine' if the bot can't send this message
            logger.debug(
                "Failed to dm user about a suggestion",
                extra={
                    "interaction.user.id": suggestion.author_id,
                    "interaction.guild.id": suggestion.guild_id,
                    "suggestion.id": suggestion_id,
                },
            )
