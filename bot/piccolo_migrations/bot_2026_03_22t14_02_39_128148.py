from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.base import OnDelete
from piccolo.columns.base import OnUpdate
from piccolo.columns.column_types import ForeignKey
from piccolo.columns.column_types import Serial
from piccolo.columns.column_types import Text
from piccolo.columns.column_types import Timestamptz
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table
from shared.tables.mixins.audit import utc_now


class UserConfigs(Table, tablename="user_configs", schema=None):
    id = Serial(
        null=False,
        primary_key=True,
        unique=False,
        index=False,
        index_method=IndexMethod.btree,
        choices=None,
        db_column_name="id",
        secret=False,
    )


ID = "2026-03-22T14:02:39:128148"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="bot", description=DESCRIPTION
    )

    manager.add_table(
        class_name="MessageAddons",
        tablename="message_addons",
        schema=None,
        columns=None,
    )

    manager.add_column(
        table_class_name="MessageAddons",
        tablename="message_addons",
        column_name="shown_message",
        db_column_name="shown_message",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": Enum(
                "PossibleMessageAddons",
                {
                    "READ_CHANGELOG": "message_addons.read_changelog",
                    "PRODUCT_UPDATES": "message_addons.product_updates",
                },
            ),
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="MessageAddons",
        tablename="message_addons",
        column_name="user",
        db_column_name="user",
        column_class_name="ForeignKey",
        column_class=ForeignKey,
        params={
            "references": UserConfigs,
            "on_delete": OnDelete.cascade,
            "on_update": OnUpdate.cascade,
            "target_column": None,
            "null": True,
            "primary_key": False,
            "unique": False,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="MessageAddons",
        tablename="message_addons",
        column_name="shown_at",
        db_column_name="shown_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    return manager
