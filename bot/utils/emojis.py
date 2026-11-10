import contextlib

import emoji as emoji_lib
import hikari


async def validate_emoji(
    rest: hikari.api.RESTClient,
    channel: hikari.SnowflakeishOr[hikari.TextableChannel],
    raw: str,
) -> hikari.CustomEmoji | hikari.UnicodeEmoji:
    """Parse ``raw`` and confirm the bot can react with it."""
    raw = raw.strip()
    if not raw:
        msg = "menus.guild_configuration.premium_menu.responses.invalid_custom_emoji"
        raise ValueError(msg)

    emoji_id: hikari.UndefinedOr[hikari.Snowflake] = hikari.UNDEFINED

    try:
        custom = hikari.CustomEmoji.parse(raw)
    except ValueError:
        converted = emoji_lib.emojize(raw, language="alias")
        if not emoji_lib.is_emoji(converted):
            msg = "menus.guild_configuration.premium_menu.responses.invalid_custom_emoji"
            raise ValueError(msg) from None

        parsed = hikari.UnicodeEmoji.parse(converted)
        reaction: str = converted
    else:
        parsed = custom
        reaction: str = custom.name
        emoji_id = custom.id

    message = None
    try:
        message = await rest.create_message(
            channel,
            "Checking emoji. This message should be automatically deleted shortly.",
        )
        await rest.add_reaction(channel, message, reaction, emoji_id)
    except hikari.ForbiddenError as exc:
        msg = (
            "menus.guild_configuration.premium_menu.responses"
            ".invalid_custom_emoji.missing_channel_perms"
        )
        raise ValueError(msg) from exc
    except (hikari.BadRequestError, hikari.NotFoundError) as exc:
        msg = (
            "menus.guild_configuration.premium_menu.responses"
            ".invalid_custom_emoji.missing_emoji_perms"
        )
        raise ValueError(msg) from exc
    finally:
        if message is not None:
            with contextlib.suppress(hikari.HTTPError):
                await rest.delete_message(channel, message)

    return parsed


def emoji_to_db(emoji: hikari.CustomEmoji | hikari.UnicodeEmoji) -> str:
    """Serialise for db."""
    if isinstance(emoji, hikari.CustomEmoji):
        return emoji.mention  # "<:name:id>" or "<a:name:id>"
    return str(emoji)  # "👍"


def emoji_from_db(value: str) -> hikari.CustomEmoji | hikari.UnicodeEmoji:
    """Deserialize from the stored varchar to send to discord."""
    try:
        return hikari.CustomEmoji.parse(value)
    except ValueError:
        return hikari.UnicodeEmoji.parse(value)
