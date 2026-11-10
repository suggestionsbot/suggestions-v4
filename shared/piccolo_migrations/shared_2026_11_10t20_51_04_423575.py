from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Varchar
from piccolo.columns.indexes import IndexMethod

ID = "2026-11-10T20:51:04:423575"
VERSION = "1.38.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="down_vote_emoji",
        db_column_name="down_vote_emoji",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 65,
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
        column_name="neutral_vote_emoji",
        db_column_name="neutral_vote_emoji",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 65,
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
        column_name="up_vote_emoji",
        db_column_name="up_vote_emoji",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 65,
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
