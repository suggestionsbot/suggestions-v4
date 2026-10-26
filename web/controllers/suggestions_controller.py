"""Web views of suggestions, laid out like the bot's Discord embed."""

import datetime as dt
import logging
import re

import hikari
import httpx
from litestar import Controller, get
from litestar.exceptions import NotFoundException
from litestar.response import Template

from bot.utils.users import fetch_user_avatar
from shared.tables import Suggestions
from shared.tables.suggestion import SuggestionStateEnum
from web import constants
from web.guards import ensure_user_is_in_guild
from web.middleware import EnsureAuth
from web.util import html_template

logger = logging.getLogger(__name__)

# generate_author_text() (bot/utils/embeds.py) stores "Name (<@123>)" or "Anonymous".
# Rows migrated from v3 store just "<@123>".
_AUTHOR_TEXT = re.compile(
    r"^(?:(?P<name>.*?)\s*\(<@!?(?P<paren_id>\d+)>\)|<@!?(?P<user_id>\d+)>)\s*$",
    re.DOTALL,
)


def person(display_text: str | None) -> dict:
    """'Vixen (<@123>)' -> {"name": "Vixen", "mention": "Vixen", "user_id": 123}.

    Missing text is "Unknown". Anonymous (or unparseable) text gets no mention,
    which the template shows as just the name. Discord would show the account's
    username in the mention; we only store the display name, so it's used for both.
    With no stored name ("<@123>", or "None (<@123>)" when Discord gave none) we
    have nothing better than the id: name None, mention "123".
    """
    if not display_text:
        return {"name": "Unknown", "mention": None, "user_id": None}
    match = _AUTHOR_TEXT.match(display_text)
    if match is None:
        return {"name": display_text, "mention": None, "user_id": None}
    user_id = match["paren_id"] or match["user_id"]
    name = match["name"] if match["name"] not in (None, "", "None") else None
    return {"name": name, "mention": name or user_id, "user_id": int(user_id)}


async def avatar_url(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        try:
            url = await fetch_user_avatar(user_id, rest=client)
        except (hikari.HTTPError, httpx.HTTPError):
            return None
    return None if url is None else str(url)


def timestamp(value: dt.datetime | None) -> dict | None:
    """What dc.time() needs: unix for the script, readable UTC text without JS."""
    if value is None:
        return None
    value = value.astimezone(dt.UTC)
    return {
        "unix": value.timestamp(),
        "iso": value.isoformat(),
        "text": value.strftime("%d %b %Y, %H:%M UTC"),
    }


async def suggestion_context(suggestion: Suggestions) -> dict:
    """Everything templates/guilds/suggestions/suggestion_embed.jinja needs."""
    # "Anonymous" has no mention or user id, so it also gets no avatar, as in Discord.
    submitter = person(suggestion.author_display_name)
    submitter["avatar_url"] = await avatar_url(submitter["user_id"])

    up_votes, down_votes = await suggestion.vote_counts()
    return {
        "suggestion": suggestion,
        "submitter": submitter,
        "moderator": person(suggestion.moderator_note_added_by_display_text),
        "resolved_by": person(suggestion.resolved_by_display_text),
        "up_votes": up_votes,
        "down_votes": down_votes,
        "thread_url": suggestion.thread_jump_link,
        "created": timestamp(suggestion.created_at),
        "resolved_at": timestamp(suggestion.resolved_at),
    }


class SuggestionController(Controller):
    middleware = [EnsureAuth]  # noqa: RUF012
    include_in_schema = False
    path = "/guilds/{guild_id:int}/suggestions"

    @get(path="/{sid:str}", name="view_suggestion", guards=[ensure_user_is_in_guild])
    async def view_suggestion(self, guild_id: int, sid: str) -> Template:
        suggestion = await Suggestions.fetch_suggestion(sid, guild_id)
        if suggestion is None or suggestion.state is SuggestionStateEnum.CLEARED:
            raise NotFoundException

        return html_template(
            "guilds/suggestions/view_suggestion.jinja",
            await suggestion_context(suggestion),
            csp_allow_discord_cdn_in_images=True,  # cached avatars
        )
