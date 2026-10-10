from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Boolean
from piccolo.columns.indexes import IndexMethod

ID = "2026-10-10T12:52:30:426316"
VERSION = "1.36.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="suggestion_button_hide_message",
        db_column_name="suggestion_button_hide_message",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
            "null": True,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    return manager
