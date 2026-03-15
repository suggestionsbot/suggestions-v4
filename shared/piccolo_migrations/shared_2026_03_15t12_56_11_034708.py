from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from hikari.locales import Locale
from piccolo.columns.column_types import Text
from piccolo.columns.column_types import Varchar
from piccolo.columns.indexes import IndexMethod


ID = "2026-03-15T12:56:11:034708"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="UserConfigs",
        tablename="user_configs",
        column_name="primary_language_raw",
        db_column_name="primary_language_raw",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "en-GB",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": Locale,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.alter_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="state_raw",
        db_column_name="state_raw",
        params={
            "choices": Enum(
                "SuggestionStateEnum",
                {
                    "PENDING": "Pending",
                    "APPROVED": "Approved",
                    "REJECTED": "Rejected",
                    "CLEARED": "Cleared",
                    "IMPLEMENTED": "Implemented",
                    "DUPLICATE": "Duplicate",
                },
            )
        },
        old_params={
            "choices": Enum(
                "SuggestionStateEnum",
                {
                    "PENDING": "Pending",
                    "APPROVED": "Approved",
                    "REJECTED": "Rejected",
                    "CLEARED": "Cleared",
                },
            )
        },
        column_class=Varchar,
        old_column_class=Varchar,
        schema=None,
    )

    return manager
