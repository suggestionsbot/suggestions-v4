from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-02-09T21:43:05:611910"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        old_column_name="state",
        new_column_name="state_raw",
        old_db_column_name="state",
        new_db_column_name="state_raw",
        schema=None,
    )

    return manager
