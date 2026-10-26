"""Web views of suggestions, laid out like the bot's Discord embed."""

import datetime as dt
import logging
import re

from litestar import Controller, get
from litestar.exceptions import NotFoundException
from litestar.response import Template

from shared.tables import (
    Suggestions,
    SuggestionVotes,
    SuggestionsVoteTypeEnum,
)
from shared.tables.suggestion import SuggestionStateEnum
from web import constants
from web.guards import ensure_user_is_in_guild
from web.middleware import EnsureAuth
from web.util import html_template

logger = logging.getLogger(__name__)

# generate_author_text() (bot/utils/embeds.py) stores "Name (<@123>)" or "Anonymous".
_AUTHOR_TEXT = re.compile(r"^(?P<name>.*?)\s*\(<@!?(?P<user_id>\d+)>\)\s*$", re.DOTALL)


def person(display_text: str | None) -> dict:
    """'Vixen (<@123>)' -> {"name": "Vixen", "mention": "Vixen", "user_id": 123}.

    Missing text is "Unknown". Anonymous (or unparseable) text gets no mention,
    which the template shows as just the name. Discord would show the account's
    username in the mention; we only store the display name, so it's used for both.
    """
    if not display_text:
        return {"name": "Unknown", "mention": None, "user_id": None}
    match = _AUTHOR_TEXT.match(display_text)
    if match is None:
        return {"name": display_text, "mention": None, "user_id": None}
    name = match["name"] or "Unknown"
    return {"name": name, "mention": name, "user_id": int(match["user_id"])}


async def cached_avatar_url(user_id: int | None) -> str | None:
    """The avatar the bot cached for this user (12h), without calling Discord."""
    if user_id is None:
        return None
    data = await constants.REDIS_CLIENT.get(f"avatars/{user_id}")
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return data or None


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


async def count_votes(suggestion: Suggestions) -> tuple[int, int]:
    up = await (
        SuggestionVotes.count()
        .where(SuggestionVotes.suggestion == suggestion)
        .where(SuggestionVotes.vote_type == SuggestionsVoteTypeEnum.UpVote)
    )
    down = await (
        SuggestionVotes.count()
        .where(SuggestionVotes.suggestion == suggestion)
        .where(SuggestionVotes.vote_type == SuggestionsVoteTypeEnum.DownVote)
    )
    return up, down


async def suggestion_context(suggestion: Suggestions) -> dict:
    """Everything templates/guilds/suggestions/suggestion_embed.jinja needs."""
    # "Anonymous" has no mention or user id, so it also gets no avatar, as in Discord.
    submitter = person(suggestion.author_display_name)
    submitter["avatar_url"] = await cached_avatar_url(submitter["user_id"])

    up_votes, down_votes = await count_votes(suggestion)
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
