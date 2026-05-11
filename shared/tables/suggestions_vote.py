from enum import Enum
from typing import Self

from piccolo.columns import Serial, ForeignKey, BigInt, Varchar, LazyTableReference
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from shared.tables.mixins import AuditMixin


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
    vote_type = Varchar(
        length=8,
        choices=SuggestionsVoteTypeEnum,
        index_method=IndexMethod.hash,
        index=True,
    )

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
