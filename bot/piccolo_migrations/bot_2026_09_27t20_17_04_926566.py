from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import JSONB
from piccolo.columns.indexes import IndexMethod

ID = "2026-09-27T20:17:04:926566"
VERSION = "1.36.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="bot", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="message_addons",
        db_column_name="message_addons",
        column_class_name="JSONB",
        column_class=JSONB,
        params={
            "default": "{}",
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
