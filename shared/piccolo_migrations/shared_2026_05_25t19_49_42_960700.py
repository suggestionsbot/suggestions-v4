from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import BigInt

ID = "2026-05-25T19:49:42:960700"
VERSION = "1.33.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="channel_id",
        db_column_name="channel_id",
        params={"index": True},
        old_params={"index": False},
        column_class=BigInt,
        old_column_class=BigInt,
        schema=None,
    )

    manager.alter_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="message_id",
        db_column_name="message_id",
        params={"index": True},
        old_params={"index": False},
        column_class=BigInt,
        old_column_class=BigInt,
        schema=None,
    )

    return manager
