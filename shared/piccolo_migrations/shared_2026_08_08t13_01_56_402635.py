from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Integer

ID = "2026-08-08T13:01:56:402635"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="cooldown_amount",
        db_column_name="cooldown_amount",
        params={"default": None, "null": True},
        old_params={"default": 22, "null": False},
        column_class=Integer,
        old_column_class=Integer,
        schema=None,
    )

    return manager
