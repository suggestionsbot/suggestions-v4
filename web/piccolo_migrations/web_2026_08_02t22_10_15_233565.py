from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text
from piccolo.columns.indexes import IndexMethod

ID = "2026-08-02T22:10:15:233565"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="subscription_item_id",
        db_column_name="subscription_item_id",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": True,
            "index_method": IndexMethod.hash,
            "choices": None,
            "db_column_name": None,
            "secret": True,
        },
        schema=None,
    )

    return manager
