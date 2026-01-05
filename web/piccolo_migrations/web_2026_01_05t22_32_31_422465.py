from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import BigInt
from piccolo.columns.column_types import Text


ID = "2026-01-05T22:32:31:422465"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="web", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="OAuthEntry",
        tablename="oauth_entry",
        column_name="oauth_id",
        db_column_name="oauth_id",
        params={"default": 0},
        old_params={"default": ""},
        column_class=BigInt,
        old_column_class=Text,
        schema=None,
    )

    return manager
