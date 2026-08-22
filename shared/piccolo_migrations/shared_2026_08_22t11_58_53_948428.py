from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text
from piccolo.columns.indexes import IndexMethod

ID = "2026-08-22T11:58:53:948428"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="suggestion_button_message",
        db_column_name="suggestion_button_message",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": None,
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

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="suggestion_button_message_prefix",
        db_column_name="suggestion_button_message_prefix",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": None,
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
