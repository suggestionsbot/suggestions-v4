from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import Varchar

ID = "2026-11-09T18:25:13:069126"
VERSION = "1.38.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
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
