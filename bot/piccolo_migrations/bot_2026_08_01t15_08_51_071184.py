from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Integer
from piccolo.columns.column_types import JSONB
from piccolo.columns.column_types import Timestamptz
from piccolo.columns.defaults.timestamptz import TimestamptzNow
from piccolo.columns.indexes import IndexMethod
from shared.tables.mixins.audit import utc_now

ID = "2026-08-01T15:08:51:071184"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="bot", description=DESCRIPTION
    )

    manager.add_table(
        class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        schema=None,
        columns=None,
    )

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="total_users_seen",
        db_column_name="total_users_seen",
        column_class_name="Integer",
        column_class=Integer,
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
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="total_guilds_seen",
        db_column_name="total_guilds_seen",
        column_class_name="Integer",
        column_class=Integer,
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
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="total_voters_seen",
        db_column_name="total_voters_seen",
        column_class_name="Integer",
        column_class=Integer,
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
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="total_users_who_only_voted",
        db_column_name="total_users_who_only_voted",
        column_class_name="Integer",
        column_class=Integer,
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
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="actions",
        db_column_name="actions",
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

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="action_types",
        db_column_name="action_types",
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

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="user_locales",
        db_column_name="user_locales",
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

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="guild_locales",
        db_column_name="guild_locales",
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

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="raw_data",
        db_column_name="raw_data",
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

    manager.add_column(
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
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
        table_class_name="AggregateCommandInvokes",
        tablename="aggregate_command_invokes",
        column_name="data_for_week_starting",
        db_column_name="data_for_week_starting",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
