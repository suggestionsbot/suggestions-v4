from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-03-02T20:06:21:827242"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        old_column_name="dm_messages_disabled",
        new_column_name="generic_dm_messages_disabled",
        old_db_column_name="dm_messages_disabled",
        new_db_column_name="generic_dm_messages_disabled",
        schema=None,
    )

    manager.rename_column(
        table_class_name="UserConfigs",
        tablename="user_configs",
        old_column_name="dm_messages_disabled",
        new_column_name="generic_dm_messages_disabled",
        old_db_column_name="dm_messages_disabled",
        new_db_column_name="generic_dm_messages_disabled",
        schema=None,
    )

    return manager
