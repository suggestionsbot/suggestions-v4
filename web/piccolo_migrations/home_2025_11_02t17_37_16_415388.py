from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2025-11-02T17:37:16:415388"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="home", description=DESCRIPTION
    )

    manager.drop_column(
        table_class_name="Users",
        tablename="users",
        column_name="staff",
        db_column_name="staff",
        schema=None,
    )

    return manager
