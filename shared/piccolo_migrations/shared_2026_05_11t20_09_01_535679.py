from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Varchar
from piccolo.columns.indexes import IndexMethod

ID = "2026-05-11T20:09:01:535679"
VERSION = "1.33.0"
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
        params={"index": False, "index_method": IndexMethod.btree},
        old_params={"index": True, "index_method": IndexMethod.hash},
        column_class=Varchar,
        old_column_class=Varchar,
        schema=None,
    )

    return manager
