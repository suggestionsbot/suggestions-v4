from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text

ID = "2026-08-21T19:29:37:430991"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="subscription_id",
        db_column_name="subscription_id",
        params={"secret": False},
        old_params={"secret": True},
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    manager.alter_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="subscription_item_id",
        db_column_name="subscription_item_id",
        params={"secret": False},
        old_params={"secret": True},
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    return manager
