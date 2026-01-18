from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-01-18T21:03:00:101619"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="GuildTokens",
        tablename="guild_tokens",
        old_column_name="checkout_session_id",
        new_column_name="subscription_id",
        old_db_column_name="checkout_session_id",
        new_db_column_name="subscription_id",
        schema=None,
    )

    return manager
