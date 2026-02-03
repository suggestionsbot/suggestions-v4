from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Array
from piccolo.columns.column_types import Text
from piccolo.columns.indexes import IndexMethod


ID = "2026-02-03T20:45:26:984587"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.drop_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="image_url",
        db_column_name="image_url",
        schema=None,
    )

    manager.drop_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="image_url",
        db_column_name="image_url",
        schema=None,
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="image_urls",
        db_column_name="image_urls",
        column_class_name="Array",
        column_class=Array,
        params={
            "default": [],
            "base_column": Text(
                default="",
                null=False,
                primary_key=False,
                unique=False,
                index=False,
                index_method=IndexMethod.btree,
                choices=None,
                db_column_name=None,
                secret=False,
            ),
            "null": True,
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

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="image_urls",
        db_column_name="image_urls",
        column_class_name="Array",
        column_class=Array,
        params={
            "default": [],
            "base_column": Text(
                default="",
                null=False,
                primary_key=False,
                unique=False,
                index=False,
                index_method=IndexMethod.btree,
                choices=None,
                db_column_name=None,
                secret=False,
            ),
            "null": True,
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
