from __future__ import annotations

import datetime
from typing import Optional


class QueuedSuggestion:
    def __init__(
        self,
        guild_id: int,
        suggestion: str,
        suggestion_author_id: int,
        created_at: datetime.datetime,
        *,
        _id: Optional[str] = None,
        is_anonymous: bool = False,
        still_in_queue: bool = True,
        image_url: Optional[str] = None,
        resolved_by: Optional[int] = None,
        resolution_note: Optional[str] = None,
        resolved_at: Optional[datetime.datetime] = None,
        related_suggestion_id: Optional[str] = None,
        message_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        guild_config_id=None,
        user_config_id=None,
        **kwargs,
    ):
        self._id: str = _id
        self.guild_id: int = guild_id
        self.suggestion: str = suggestion
        self.is_anonymous: bool = is_anonymous
        self.image_url: Optional[str] = image_url
        self.still_in_queue: bool = still_in_queue
        self.channel_id: Optional[int] = channel_id
        self.message_id: Optional[int] = message_id
        self.resolved_by: Optional[int] = resolved_by
        self.created_at: datetime.datetime = created_at
        self.suggestion_author_id: int = suggestion_author_id
        # For example saying why it didn't get approved
        self.resolution_note: Optional[str] = resolution_note
        self.resolved_at: Optional[datetime.datetime] = resolved_at

        # If this queued suggestion get approved,
        # this field will be the id of the created suggestion
        self.related_suggestion_id: Optional[str] = related_suggestion_id

        self.user_config_id = user_config_id
        self.guild_config_id = guild_config_id


import datetime
import logging
from enum import Enum
from typing import TYPE_CHECKING, Literal, Union, Optional, cast

logger = logging.getLogger(__name__)


class SuggestionState(Enum):
    pending = 0
    approved = 1
    rejected = 2
    cleared = 3

    @staticmethod
    def from_str(value: str) -> SuggestionState:
        mappings = {
            "pending": SuggestionState.pending,
            "approved": SuggestionState.approved,
            "rejected": SuggestionState.rejected,
            "cleared": SuggestionState.cleared,
        }
        return mappings[value.lower()]

    def as_str(self) -> str:
        if self is SuggestionState.rejected:
            return "rejected"

        elif self is SuggestionState.approved:
            return "approved"

        elif self is SuggestionState.cleared:
            return "cleared"

        return "pending"


class Suggestion:
    """An abstract wrapper encapsulating all suggestion functionality."""

    def __init__(
        self,
        _id: str,
        guild_id: int,
        suggestion: str,
        suggestion_author_id: int,
        created_at: datetime.datetime,
        state: Union[
            Literal["open", "approved", "rejected", "cleared"],
            SuggestionState,
        ],
        *,
        note: Optional[str] = None,
        note_added_by: Optional[int] = None,
        total_up_votes: Optional[int] = None,
        total_down_votes: Optional[int] = None,
        up_voted_by: Optional[list[int]] = None,
        down_voted_by: Optional[list[int]] = None,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
        resolved_by: Optional[int] = None,
        resolution_note: Optional[str] = None,
        resolved_at: Optional[datetime.datetime] = None,
        image_url: Optional[str] = None,
        uses_views_for_votes: bool = False,
        is_anonymous: bool = False,
        anonymous_resolution: Optional[bool] = None,
        thread_id: Optional[int] = None,
        guild_config_id=None,
        user_config_id=None,
        **kwargs,
    ):
        self._id: str = _id
        self.guild_id: int = guild_id
        self.suggestion: str = suggestion
        self.suggestion_author_id: int = suggestion_author_id
        self.created_at: datetime.datetime = created_at
        self.state: SuggestionState = (
            SuggestionState.from_str(state)
            if not isinstance(state, SuggestionState)
            else state
        )
        self.uses_views_for_votes: bool = uses_views_for_votes

        self.channel_id: Optional[int] = channel_id
        self.message_id: Optional[int] = message_id
        self.thread_id: Optional[int] = thread_id
        self.resolved_by: Optional[int] = resolved_by
        self.resolved_at: Optional[datetime.datetime] = resolved_at
        self.resolution_note: Optional[str] = resolution_note
        self._total_up_votes: Optional[int] = total_up_votes
        self._total_down_votes: Optional[int] = total_down_votes
        self.up_voted_by: set[int] = set(up_voted_by) if up_voted_by else set()
        self.down_voted_by: set[int] = set(down_voted_by) if down_voted_by else set()
        self.image_url: Optional[str] = image_url
        self.is_anonymous: bool = is_anonymous
        self.anonymous_resolution: Optional[bool] = anonymous_resolution
        self.note: Optional[str] = note
        self.note_added_by: Optional[int] = note_added_by
        self.user_config_id = user_config_id
        self.guild_config_id = guild_config_id

    def as_dict(self) -> dict:
        data = {
            "guild_id": self.guild_id,
            "state": self.state.as_str(),
            "suggestion": self.suggestion,
            "_id": self._id,
            "suggestion_author_id": self.suggestion_author_id,
            "created_at": self.created_at,
            "uses_views_for_votes": self.uses_views_for_votes,
            "is_anonymous": self.is_anonymous,
            "anonymous_resolution": self.anonymous_resolution,
        }

        if self.note:
            data["note"] = self.note
            data["note_added_by"] = self.note_added_by

        if self.resolved_by:
            data["resolved_by"] = self.resolved_by
            data["resolution_note"] = self.resolution_note

        if self.resolved_at:
            data["resolved_at"] = self.resolved_at

        if self.message_id:
            data["message_id"] = self.message_id

        if self.channel_id:
            data["channel_id"] = self.channel_id

        if self.thread_id:
            data["thread_id"] = self.thread_id

        if self.uses_views_for_votes:
            data["up_voted_by"] = list(self.up_voted_by)
            data["down_voted_by"] = list(self.down_voted_by)

        else:
            data["total_up_votes"] = self._total_up_votes
            data["total_down_votes"] = self._total_down_votes

        if self.image_url is not None:
            data["image_url"] = self.image_url

        data["user_config_id"] = self.user_config_id
        data["guild_config_id"] = self.guild_config_id

        return data
