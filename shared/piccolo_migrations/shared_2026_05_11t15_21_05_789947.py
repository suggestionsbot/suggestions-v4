from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import Varchar

ID = "2026-05-11T15:21:05:789947"
VERSION = "1.33.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="state_raw",
        db_column_name="state_raw",
        params={
            "choices": Enum(
                "QueuedSuggestionStateEnum",
                {
                    "PENDING": "Pending",
                    "APPROVED": "Approved",
                    "REJECTED": "Rejected",
                    "CLEARED": "Cleared",
                },
            )
        },
        old_params={
            "choices": Enum(
                "QueuedSuggestionStateEnum",
                {
                    "PENDING": "Pending",
                    "APPROVED": "Approved",
                    "REJECTED": "Rejected",
                },
            )
        },
        column_class=Varchar,
        old_column_class=Varchar,
        schema=None,
    )

    return manager
