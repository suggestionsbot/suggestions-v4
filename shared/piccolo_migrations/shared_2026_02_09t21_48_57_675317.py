from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import ForeignKey


ID = "2026-02-09T21:48:57:675317"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        old_column_name="state_raw",
        new_column_name="state",
        old_db_column_name="state_raw",
        new_db_column_name="state",
        schema=None,
    )

    manager.alter_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="moderator_note_added_by",
        db_column_name="moderator_note_added_by",
        params={"secret": True},
        old_params={"secret": False},
        column_class=ForeignKey,
        old_column_class=ForeignKey,
        schema=None,
    )

    return manager
