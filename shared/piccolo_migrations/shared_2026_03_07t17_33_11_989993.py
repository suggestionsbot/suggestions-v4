from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-03-07T17:33:11:989993"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        old_column_name="anonymous_resolutions",
        new_column_name="allow_anonymous_moderators",
        old_db_column_name="anonymous_resolutions",
        new_db_column_name="allow_anonymous_moderators",
        schema=None,
    )

    return manager
