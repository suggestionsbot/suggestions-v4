from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import Boolean
from piccolo.columns.column_types import Varchar
from piccolo.columns.indexes import IndexMethod

ID = "2026-11-09T20:32:11:668532"
VERSION = "1.38.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="allow_neutral_votes",
        db_column_name="allow_neutral_votes",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.alter_column(
        table_class_name="SuggestionVotes",
        tablename="suggestion_votes",
        column_name="vote_type",
        db_column_name="vote_type",
        params={
            "length": 11,
            "choices": Enum(
                "SuggestionsVoteTypeEnum",
                {
                    "UpVote": "UpVote",
                    "DownVote": "DownVote",
                    "NeutralVote": "NeutralVote",
                },
            ),
        },
        old_params={
            "length": 8,
            "choices": Enum(
                "SuggestionsVoteTypeEnum",
                {"UpVote": "UpVote", "DownVote": "DownVote"},
            ),
        },
        column_class=Varchar,
        old_column_class=Varchar,
        schema=None,
    )

    return manager
