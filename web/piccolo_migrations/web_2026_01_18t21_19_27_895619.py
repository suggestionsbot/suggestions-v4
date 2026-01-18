from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Timestamptz
from piccolo.columns.defaults.timestamptz import TimestamptzNow
from piccolo.columns.indexes import IndexMethod


ID = "2026-01-18T21:19:27:895619"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.drop_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="is_valid",
        db_column_name="is_valid",
        schema=None,
    )

    manager.add_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="expires_at",
        db_column_name="expires_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
            "null": False,
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
