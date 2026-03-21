from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Varchar


ID = "2026-03-21T13:26:37:996837"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="state_raw",
        db_column_name="state_raw",
        params={"default": "Pending"},
        old_params={"default": ""},
        column_class=Varchar,
        old_column_class=Varchar,
        schema=None,
    )

    return manager
