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
        lock_rows: bool = False,
    ) -> tuple[SuggestionVotes, bool]:
        created = False
        query = SuggestionVotes.objects().first()
        if lock_rows:
            query = query.lock_rows("UPDATE", of=(cls,))

        query = query.where(
            Where(
                SuggestionVotes.suggestion,
                suggestion,
                operator=Equal,
            )
        ).where(
            Where(
                SuggestionVotes.user_id,
                user_id,
                operator=Equal,
            )
        )
        vote_obj = await query
        if vote_obj is None:
            created = True
            vote_obj = cls(suggestion=suggestion, user_id=user_id, vote_type=vote_type)
            await vote_obj.save()

        return vote_obj, created
