from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-02-14T14:41:19:193023"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        old_column_name="uses_suggestions_queue",
        new_column_name="uses_suggestion_queue",
        old_db_column_name="uses_suggestions_queue",
        new_db_column_name="uses_suggestion_queue",
        schema=None,
    )

    return manager
