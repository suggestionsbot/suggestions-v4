from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import JSON


ID = "2026-02-14T14:58:22:164668"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="blocked_users_json",
        db_column_name="blocked_users_json",
        params={"default": None, "null": True},
        old_params={"default": "{}", "null": False},
        column_class=JSON,
        old_column_class=JSON,
        schema=None,
    )

    return manager
