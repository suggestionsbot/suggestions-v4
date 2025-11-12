from enum import Enum

from piccolo.columns import Serial, ForeignKey, BigInt, Varchar, LazyTableReference
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from shared.tables.mixins import AuditMixin


class SuggestionsVoteTypeEnum(Enum):
    UpVote = "UpVote"
    DownVote = "DownVote"


class SuggestionsVote(Table, AuditMixin):
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
    user_id = BigInt(index=True)
    # Currently just up vote and down vote but this is future proofing
    vote_type = Varchar(
        length=8,
        choices=SuggestionsVoteTypeEnum,
        index_method=IndexMethod.hash,
        index=True,
    )
