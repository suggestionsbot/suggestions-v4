from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text


ID = "2026-01-18T18:47:45:210003"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="checkout_session_id",
        db_column_name="checkout_session_id",
        params={"secret": True},
        old_params={"secret": False},
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    return manager
