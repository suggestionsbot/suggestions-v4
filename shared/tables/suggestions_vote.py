from __future__ import annotations

from enum import Enum
from typing import Self, TYPE_CHECKING

from piccolo.columns import (
    Serial,
    ForeignKey,
    BigInt,
    Varchar,
    LazyTableReference,
    Where,
)
from piccolo.columns.operators import Equal
from piccolo.table import Table

from shared.tables.mixins import AuditMixin

if TYPE_CHECKING:
    from shared.tables import Suggestions


class SuggestionsVoteTypeEnum(Enum):
    UpVote = "UpVote"
    DownVote = "DownVote"


class SuggestionVotes(Table, AuditMixin):
    id = Serial(
        primary_key=True,
        unique=True,
        index=True,
    )
    suggestion = ForeignKey(
        LazyTableReference(
            table_class_name="Suggestions",
            app_name="shared",
        ),
        index=True,
    )
    user_id = BigInt(index=True, help_text="Who put this vote down")
    # Currently just up vote and down vote but this is future proofing
    vote_type = Varchar(length=8, choices=SuggestionsVoteTypeEnum)

    @property
    def vote_type_enum(self) -> SuggestionsVoteTypeEnum:
        return SuggestionsVoteTypeEnum(self.vote_type)

    @vote_type_enum.setter
    def vote_type_enum(self, value: SuggestionsVoteTypeEnum) -> None:
        self.vote_type = value.value

    @classmethod
    async def fetch_votes_for_suggestion(
        cls, suggestion, *, vote_type: SuggestionsVoteTypeEnum | None = None
    ) -> list[Self]:
        query = cls.objects().where(cls.suggestion == suggestion)
        if vote_type is not None:
            query = query.where(cls.vote_type == vote_type)

        return await query

    @classmethod
    async def get_or_create(
        cls,
        *,
        suggestion: Suggestions,
        vote_type: SuggestionsVoteTypeEnum,
        user_id: int,
    ) -> tuple[SuggestionVotes, bool]:
        try_insert = (
            await SuggestionVotes.insert(
                cls(suggestion=suggestion, user_id=user_id, vote_type=vote_type)
            )
            .on_conflict(action="DO NOTHING", target=(cls.user_id, cls.suggestion))
            .returning(*SuggestionVotes.all_columns())
        )
        if try_insert:
            # New object
            obj = cls(**try_insert[0])
            obj._exists_in_db = True
            return obj, True

        return (
            await SuggestionVotes.objects()
            .first()
            .where(
                Where(
                    SuggestionVotes.suggestion,
                    suggestion,
                    operator=Equal,
                )
            )
            .where(
                Where(
                    SuggestionVotes.user_id,
                    user_id,
                    operator=Equal,
                )
            ),
            False,
        )
