import logging

from bot.constants import LOCALISATIONS
from datetime import timedelta

import hikari

from bot import utils
from web import constants
from shared.tables import GuildConfigs
from shared.utils import configs

logger = logging.getLogger(__name__)


async def notify_guild_of_missing_suggestion_permissions(_, guild_id: int) -> None:
    """Notify a guild that the bot is missing permissions to edit suggestions."""
    has_been_sent_key: str = f"errors:missing_suggestion_perms_sent:{guild_id}"
    has_been_sent = await constants.REDIS_CLIENT.get(has_been_sent_key)
    if has_been_sent:
        # We don't want to spam messages
        logger.debug(
            "Ignoring notify_guild_of_missing_suggestion_permissions as we "
            "already have notified this guild recently",
            extra={"guild.id": guild_id},
        )
        return

    guild_config: GuildConfigs = await configs.ensure_guild_config(guild_id)
    if guild_config.update_channel_id is not None:
        # Try just send a message first
        try:
            async with constants.DISCORD_REST_CLIENT.acquire(
                constants.BOT_TOKEN, hikari.TokenType.BOT
            ) as client:
                await client.create_message(
                    guild_config.update_channel_id,
                    embed=utils.error_embed(
                        LOCALISATIONS.get_localized_string(
                            "errors.missing_suggestion_edit_permissions.title",
                            guild_config.primary_language,
                        ),
                        LOCALISATIONS.get_localized_string(
                            "errors.missing_suggestion_edit_permissions.description",
                            guild_config.primary_language,
                        ),
                    ),
                )
        except hikari.HikariError:
            # We can just let the fallback method handle this
            pass
        else:
            await constants.REDIS_CLIENT.set(
                has_been_sent_key,
                guild_config.guild_id,
                ex=timedelta(hours=6),
            )
            logger.debug(
                "Send message to guild update channel about missing permissions",
                extra={"guild.id": guild_id},
            )
            return

    # By this point put a message in redis and on next
    # vote we will tell the user to bring it up
    need_to_tell_user: str = f"errors:missing_suggestion_perms:{guild_id}"
    await constants.REDIS_CLIENT.set(
        need_to_tell_user,
        guild_config.guild_id,
        ex=timedelta(hours=6),
    )
    logger.debug(
        "Send message to guild update channel about missing permissions",
        extra={"guild.id": guild_id},
    )
