from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-01-13T21:01:18:233818"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        old_column_name="primary_language",
        new_column_name="primary_language_raw",
        old_db_column_name="primary_language",
        new_db_column_name="primary_language_raw",
        schema=None,
    )

    return manager
