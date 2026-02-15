from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text


ID = "2026-02-14T15:26:49:711294"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="suggestions_prefix",
        db_column_name="suggestions_prefix",
        params={"default": None, "null": True},
        old_params={"default": "", "null": False},
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    manager.alter_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="queued_suggestions_prefix",
        db_column_name="queued_suggestions_prefix",
        params={"default": None, "null": True},
        old_params={"default": "", "null": False},
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    return manager
