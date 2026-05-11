from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import Text

ID = "2026-05-11T20:09:57:561142"
VERSION = "1.33.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="bot", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="action_type",
        db_column_name="action_type",
        params={
            "choices": Enum(
                "CommandTypes",
                {
                    "SLASH_COMMAND": "Slash Command",
                    "MESSAGE_COMMAND": "Message Command",
                    "BUTTON": "Button",
                    "OTHER": "Other",
                },
            )
        },
        old_params={
            "choices": Enum(
                "CommandTypes",
                {"SLASH": "Slash Command", "BUTTON": "Button", "OTHER": "Other"},
            )
        },
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    return manager
