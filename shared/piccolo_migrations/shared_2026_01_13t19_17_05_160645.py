from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from hikari.locales import Locale
from piccolo.columns.column_types import Text
from piccolo.columns.indexes import IndexMethod


ID = "2026-01-13T19:17:05:160645"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="primary_language",
        db_column_name="primary_language",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "en-GB",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": Locale,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    return manager
