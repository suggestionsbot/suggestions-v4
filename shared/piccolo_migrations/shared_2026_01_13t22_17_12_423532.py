from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Boolean


ID = "2026-01-13T22:17:12:423532"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="can_have_anonymous_suggestions",
        db_column_name="can_have_anonymous_suggestions",
        params={"default": True},
        old_params={"default": False},
        column_class=Boolean,
        old_column_class=Boolean,
        schema=None,
    )

    return manager
