from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Boolean

ID = "2026-06-14T15:33:33:939128"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="auto_archive_threads",
        db_column_name="auto_archive_threads",
        params={"default": True},
        old_params={"default": False},
        column_class=Boolean,
        old_column_class=Boolean,
        schema=None,
    )

    return manager
