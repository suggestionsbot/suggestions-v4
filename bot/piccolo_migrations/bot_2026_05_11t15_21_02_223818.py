from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from enum import Enum
from piccolo.columns.column_types import BigInt
from piccolo.columns.column_types import Text
from piccolo.columns.column_types import Timestamptz
from piccolo.columns.indexes import IndexMethod
from shared.tables.mixins.audit import utc_now

ID = "2026-05-11T15:21:02:223818"
VERSION = "1.33.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(migration_id=ID, app_name="bot", description=DESCRIPTION)

    manager.add_table(
        class_name="CommandInvokes",
        tablename="command_invokes",
        schema=None,
        columns=None,
    )

    manager.add_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="command",
        db_column_name="command",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
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

    manager.add_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="command_type",
        db_column_name="command_type",
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
                "CommandTypes",
                {"SLASH": "Slash Command", "BUTTON": "Button", "OTHER": "Other"},
            ),
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="created_at",
        db_column_name="created_at",
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

    manager.add_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="user_locale",
        db_column_name="user_locale",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
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

    manager.add_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="guild_locale",
        db_column_name="guild_locale",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": None,
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
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="user_id",
        db_column_name="user_id",
        column_class_name="BigInt",
        column_class=BigInt,
        params={
            "default": 0,
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

    manager.add_column(
        table_class_name="CommandInvokes",
        tablename="command_invokes",
        column_name="guild_id",
        db_column_name="guild_id",
        column_class_name="BigInt",
        column_class=BigInt,
        params={
            "default": None,
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
                    "LEGACY_RESOLUTION_COMMANDS": "message_addons.legacy_resolution_commands",
                },
            )
        },
        old_params={
            "choices": Enum(
                "PossibleMessageAddons",
                {
                    "READ_CHANGELOG": "message_addons.read_changelog",
                    "PRODUCT_UPDATES": "message_addons.product_updates",
                    "SUGGESTION_RESOLUTION_NOTIFICATIONS": "message_addons.premium.notif_on_suggestion_resolution",
                },
            )
        },
        column_class=Text,
        old_column_class=Text,
        schema=None,
    )

    return manager
