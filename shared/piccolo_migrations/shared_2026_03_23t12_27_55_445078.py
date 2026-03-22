from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-03-23T12:27:55:445078"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.drop_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="still_in_queue",
        db_column_name="still_in_queue",
        schema=None,
    )

    return manager
