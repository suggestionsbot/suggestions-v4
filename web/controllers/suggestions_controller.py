"""Web views of suggestions, rendered exactly as the bot posts them in Discord.

The page HTML comes from the same ``Suggestions.as_components()`` the bot uses,
rendered by ``web.discord_html``, so the dashboard can never drift from what
members see in their server.
"""

import asyncio
import logging
import math
import re

import hikari
from litestar import Controller, Request, get
from litestar.exceptions import NotFoundException
from litestar.response import Template
from piccolo.columns.combination import And, Where
from piccolo.columns.operators import Equal, NotEqual

from bot.constants import IS_CUSTOM_BOT, LOCALISATIONS, EMBED_COLOR
from shared.tables import (
    GuildConfigs,
    Suggestions,
    SuggestionVotes,
    SuggestionsVoteTypeEnum,
)
from shared.tables.suggestion import SuggestionStateEnum
from shared.utils import configs
from web import constants, discord_html
from web.discord_html import colors
from web.guards import ensure_user_has_manage_permissions
from web.middleware import EnsureAuth
from web.util import html_template

logger = logging.getLogger(__name__)

# generate_author_text() (bot/utils/embeds.py) stores "Name (<@123>)" or "Anonymous".
_AUTHOR_TEXT = re.compile(r"^(?P<name>.*?)\s*\(<@!?(?P<user_id>\d+)>\)\s*$", re.DOTALL)


def person(display_text: str | None) -> dict | None:
    """'Vixen (<@123>)' -> {"name": "Vixen", "mention": "Vixen", "user_id": 123}.
    Anonymous (or unparseable) text gets no mention, which the template shows as
    just the name. Discord would show the account's username in the mention; we
    only store the display name, so it's used for both."""
    if not display_text:
        return None
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
    return data.decode("utf-8") if data else None


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


def bot_author() -> dict:
    return {
        "name": "Suggestions",
        "avatar_url": "/static/suggestion_icon.png",  # same origin: img-src 'self'
        "color": EMBED_COLOR,
        "app": True,
        "verified": not IS_CUSTOM_BOT,  # Discord only ticks the main, verified bot
    }


async def suggestion_context(suggestion: Suggestions) -> dict:
    """Everything templates/suggestions/suggestion_message.jinja needs."""
    # "Anonymous" has no mention or user id, so it also gets no avatar, as in Discord.
    submitter = person(suggestion.author_display_name) or {
        "name": "Unknown",
        "mention": None,
        "user_id": None,
    }
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
        "edited": suggestion.last_modified_at > suggestion.created_at,
        "bot": bot_author(),
    }


class SuggestionController(Controller):
    middleware = [EnsureAuth]  # noqa: RUF012
    include_in_schema = False
    path = "/guilds/{guild_id:int}/suggestions"
    # Staff only. Guild membership is not enough: a guild's suggestions or log
    # channel may be hidden from regular members in Discord, and these pages show
    # everything (including moderator notes). Opening this to members needs a
    # per-channel VIEW_CHANNEL check against the suggestion's channel first.
    guards = [ensure_user_has_manage_permissions]  # noqa: RUF012

    @get(path="/{sid:str}", name="view_suggestion")
    async def view_suggestion(
        self, request: Request, guild_id: int, sid: str
    ) -> Template:
        suggestion = await Suggestions.fetch_suggestion(sid, guild_id)
        if suggestion is None or suggestion.state is SuggestionStateEnum.CLEARED:
            raise NotFoundException

        return html_template(
            "guilds/suggestions/view_suggestion.jinja",
            await suggestion_context(suggestion),
            csp_allow_discord_cdn_in_images=True,  # cached avatars
        )
