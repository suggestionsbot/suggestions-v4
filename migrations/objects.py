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

    __slots__ = [
        "_id",
        "guild_id",
        "suggestion",
        "suggestion_author_id",
        "created_at",
        "state",
        "note",
        "note_added_by",
        "_total_up_votes",
        "_total_down_votes",
        "up_voted_by",
        "down_voted_by",
        "channel_id",
        "message_id",
        "resolved_by",
        "resolution_note",
        "resolved_at",
        "image_url",
        "uses_views_for_votes",
        "is_anonymous",
        "anonymous_resolution",
        "thread_id",
    ]

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
        **kwargs,
    ):
        """

        Parameters
        ----------
        guild_id: int
            The guild this suggestion is in
        suggestion: str
            The suggestion content itself
        _id: str
            The id of the suggestion
        suggestion_author_id: int
            The id of the person who created the suggestion
        created_at: datetime.datetime
            When this suggestion was created
        state: Union[Literal["open", "approved", "rejected"], SuggestionState]
            The current state of the suggestion itself

        Other Parameters
        ----------------
        note: Optional[str]
            A note to add to the suggestion embed
        note_added_by: Optional[int]
            Who added the note.

            Should be marked as hidden if not shown.
        resolved_by: Optional[int]
            Who changed the final state of this suggestion
        resolution_note: Optional[str]
            A note to add to the suggestion on resolve
        resolved_at: Optional[datetime.datetime]
            When this suggestion was resolved
        channel_id: Optional[int]
            The channel this suggestion is currently in
        message_id: Optional[int]
            The current message ID. This could be the suggestion
            or the log channel message.
        total_up_votes: Optional[int]
            How many up votes this had when closed

            This is based off the old reaction system.
        total_down_votes: Optional[int]
            How many down votes this had when closed

            This is based off the old reaction system.
        up_voted_by: Optional[list[int]]
            A list of people who up voted this suggestion

            This is based off the new button system
        up_voted_by: Optional[list[int]]
            A list of people who up voted this suggestion

            This is based off the new button system
        down_voted_by: Optional[list[int]]
            A list of people who down voted this suggestion

            This is based off the new button system
        image_url: Optional[str]
            An optional url for an image attached to the suggestion
        uses_views_for_votes: bool
            A simple flag to make backwards compatibility easier.

            Defaults to `False` as all old suggestions will use this
            value since they don't have the field in the database
        is_anonymous: bool
            Whether or not this suggestion
            should be displayed anonymous
        anonymous_resolution: Optional[bool]
            Whether or not to show who resolved this suggestion
            to the end suggester
        thread_id: Optional[str]
            The ID of the thread to resolve directly
        """
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
