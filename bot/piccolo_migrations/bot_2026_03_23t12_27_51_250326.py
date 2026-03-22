from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import Text


ID = "2026-03-23T12:27:51:250326"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="bot", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="MessageAddons",
        tablename="message_addons",
        column_name="shown_message",
        db_column_name="shown_message",
        params={
            "choices": Enum(
                "PossibleMessageAddons",
                {
                    "READ_CHANGELOG": "message_addons.read_changelog",
                    "PRODUCT_UPDATES": "message_addons.product_updates",
                    "SUGGESTION_RESOLUTION_NOTIFICATIONS": "message_addons.premium.notif_on_suggestion_resolution",
                },
            )
        },
        old_params={
            "choices": Enum(
                "PossibleMessageAddons",
                {
                    "READ_CHANGELOG": "message_addons.read_changelog",
                    "PRODUCT_UPDATES": "message_addons.product_updates",
                },
            )
        },
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    return manager
