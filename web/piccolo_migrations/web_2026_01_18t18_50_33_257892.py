from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import BigInt


ID = "2026-01-18T18:50:33:257892"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        column_name="used_for_guild",
        db_column_name="used_for_guild",
        params={"null": True},
        old_params={"null": False},
        column_class=BigInt,
        old_column_class=BigInt,
        schema=None,
    )

    return manager
