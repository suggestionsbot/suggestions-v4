from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-05-11T15:38:25:565390"
VERSION = "1.33.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="bot", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        old_column_name="command",
        new_column_name="action",
        old_db_column_name="command",
        new_db_column_name="action",
        schema=None,
    )

    manager.rename_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        old_column_name="command_type",
        new_column_name="action_type",
        old_db_column_name="command_type",
        new_db_column_name="action_type",
        schema=None,
    )

    return manager
