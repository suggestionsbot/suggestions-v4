from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import Varchar
from piccolo.columns.indexes import IndexMethod


ID = "2026-03-21T13:25:53:793482"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="state_raw",
        db_column_name="state_raw",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 255,
            "default": "",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": Enum(
                "QueuedSuggestionStateEnum",
                {
                    "PENDING": "Pending",
                    "APPROVED": "Approved",
                    "REJECTED": "Rejected",
                },
            ),
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    return manager
