from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from bot.utils.id import generate_id
from enum import Enum
from piccolo.columns.base import OnDelete
from piccolo.columns.base import OnUpdate
from piccolo.columns.column_types import Array
from piccolo.columns.column_types import BigInt
from piccolo.columns.column_types import Boolean
from piccolo.columns.column_types import ForeignKey
from piccolo.columns.column_types import Integer
from piccolo.columns.column_types import Serial
from piccolo.columns.column_types import Text
from piccolo.columns.column_types import Timestamptz
from piccolo.columns.column_types import Varchar
from piccolo.columns.defaults.timestamptz import TimestamptzNow
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table
from shared.tables.mixins.audit import utc_now


class GuildConfigs(Table, tablename="guild_configs", schema=None):
    guild_id = BigInt(
        default=0,
        null=False,
        primary_key=True,
        unique=True,
        index=True,
        index_method=IndexMethod.btree,
        choices=None,
        db_column_name=None,
        secret=False,
    )


class PremiumGuildConfigs(Table, tablename="premium_guild_configs", schema=None):
    guild_id = BigInt(
        default=0,
        null=False,
        primary_key=True,
        unique=True,
        index=True,
        index_method=IndexMethod.btree,
        choices=None,
        db_column_name=None,
        secret=False,
    )


class Suggestions(Table, tablename="suggestions", schema=None):
    id = Serial(
        null=False,
        primary_key=True,
        unique=True,
        index=True,
        index_method=IndexMethod.btree,
        choices=None,
        db_column_name=None,
        secret=False,
    )


class UserConfigs(Table, tablename="user_configs", schema=None):
    user_id = BigInt(
        default=0,
        null=False,
        primary_key=True,
        unique=True,
        index=True,
        index_method=IndexMethod.btree,
        choices=None,
        db_column_name=None,
        secret=False,
    )


ID = "2026-01-04T18:10:04:484784"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(migration_id=ID, app_name="shared", description=DESCRIPTION)

    manager.add_table(
        class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        schema=None,
        columns=None,
    )

    manager.add_table(
        class_name="SuggestionsVote",
        tablename="suggestions_vote",
        schema=None,
        columns=None,
    )

    manager.add_table(
        class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        schema=None,
        columns=None,
    )

    manager.add_table(
        class_name="GuildConfigs",
        tablename="guild_configs",
        schema=None,
        columns=None,
    )

    manager.add_table(
        class_name="Suggestions",
        tablename="suggestions",
        schema=None,
        columns=None,
    )

    manager.add_table(
        class_name="UserConfigs",
        tablename="user_configs",
        schema=None,
        columns=None,
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="created_at",
        db_column_name="created_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="last_modified_at",
        db_column_name="last_modified_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="id",
        db_column_name="id",
        column_class_name="Serial",
        column_class=Serial,
        params={
            "null": False,
            "primary_key": True,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="sID",
        db_column_name="sID",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 255,
            "default": generate_id,
            "null": False,
            "primary_key": False,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.hash,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="suggestion",
        db_column_name="suggestion",
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="guild_configuration",
        db_column_name="guild_configuration",
        column_class_name="ForeignKey",
        column_class=ForeignKey,
        params={
            "references": GuildConfigs,
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="user_configuration",
        db_column_name="user_configuration",
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
            "secret": True,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="channel_id",
        db_column_name="channel_id",
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

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="message_id",
        db_column_name="message_id",
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

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="still_in_queue",
        db_column_name="still_in_queue",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="related_suggestion",
        db_column_name="related_suggestion",
        column_class_name="ForeignKey",
        column_class=ForeignKey,
        params={
            "references": Suggestions,
            "on_delete": OnDelete.cascade,
            "on_update": OnUpdate.cascade,
            "target_column": None,
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="resolved_by",
        db_column_name="resolved_by",
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
            "secret": True,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="resolved_by_display_text",
        db_column_name="resolved_by_display_text",
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="resolved_note",
        db_column_name="resolved_note",
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="resolved_at",
        db_column_name="resolved_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="image_url",
        db_column_name="image_url",
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
        table_class_name="QueuedSuggestions",
        tablename="queued_suggestions",
        column_name="author_display_name",
        db_column_name="author_display_name",
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
        table_class_name="SuggestionsVote",
        tablename="suggestions_vote",
        column_name="created_at",
        db_column_name="created_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
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
        table_class_name="SuggestionsVote",
        tablename="suggestions_vote",
        column_name="last_modified_at",
        db_column_name="last_modified_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
        table_class_name="SuggestionsVote",
        tablename="suggestions_vote",
        column_name="id",
        db_column_name="id",
        column_class_name="Serial",
        column_class=Serial,
        params={
            "null": False,
            "primary_key": True,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="SuggestionsVote",
        tablename="suggestions_vote",
        column_name="suggestion",
        db_column_name="suggestion",
        column_class_name="ForeignKey",
        column_class=ForeignKey,
        params={
            "references": Suggestions,
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
        table_class_name="SuggestionsVote",
        tablename="suggestions_vote",
        column_name="user_id",
        db_column_name="user_id",
        column_class_name="BigInt",
        column_class=BigInt,
        params={
            "default": 0,
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
        table_class_name="SuggestionsVote",
        tablename="suggestions_vote",
        column_name="vote_type",
        db_column_name="vote_type",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 8,
            "default": "",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": True,
            "index_method": IndexMethod.hash,
            "choices": Enum(
                "SuggestionsVoteTypeEnum",
                {"UpVote": "UpVote", "DownVote": "DownVote"},
            ),
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="created_at",
        db_column_name="created_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
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
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="last_modified_at",
        db_column_name="last_modified_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="guild_id",
        db_column_name="guild_id",
        column_class_name="BigInt",
        column_class=BigInt,
        params={
            "default": 0,
            "null": False,
            "primary_key": True,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="suggestions_prefix",
        db_column_name="suggestions_prefix",
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
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="queued_suggestions_prefix",
        db_column_name="queued_suggestions_prefix",
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
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="cooldown_period",
        db_column_name="cooldown_period",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "Hour",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": Enum(
                "CooldownPeriod",
                {
                    "Hour": "Hour",
                    "Day": "Day",
                    "Week": "Week",
                    "Fortnight": "Fortnight",
                    "Month": "Month",
                },
            ),
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="PremiumGuildConfigs",
        tablename="premium_guild_configs",
        column_name="cooldown_amount",
        db_column_name="cooldown_amount",
        column_class_name="Integer",
        column_class=Integer,
        params={
            "default": 22,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="created_at",
        db_column_name="created_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="last_modified_at",
        db_column_name="last_modified_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="guild_id",
        db_column_name="guild_id",
        column_class_name="BigInt",
        column_class=BigInt,
        params={
            "default": 0,
            "null": False,
            "primary_key": True,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="keep_logs",
        db_column_name="keep_logs",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="dm_messages_disabled",
        db_column_name="dm_messages_disabled",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="log_channel_id",
        db_column_name="log_channel_id",
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

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="queued_suggestion_channel_id",
        db_column_name="queued_suggestion_channel_id",
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

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="queued_suggestion_log_channel_id",
        db_column_name="queued_suggestion_log_channel_id",
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

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="threads_for_suggestions",
        db_column_name="threads_for_suggestions",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="suggestions_channel_id",
        db_column_name="suggestions_channel_id",
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

    manager.add_column(
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="can_have_anonymous_suggestions",
        db_column_name="can_have_anonymous_suggestions",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="auto_archive_threads",
        db_column_name="auto_archive_threads",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="uses_suggestions_queue",
        db_column_name="uses_suggestions_queue",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="virtual_suggestions_queue",
        db_column_name="virtual_suggestions_queue",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="can_have_images_in_suggestions",
        db_column_name="can_have_images_in_suggestions",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="anonymous_resolutions",
        db_column_name="anonymous_resolutions",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="blocked_users",
        db_column_name="blocked_users",
        column_class_name="Array",
        column_class=Array,
        params={
            "default": list,
            "base_column": BigInt(
                default=0,
                null=False,
                primary_key=False,
                unique=False,
                index=False,
                index_method=IndexMethod.btree,
                choices=None,
                db_column_name=None,
                secret=False,
            ),
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="ping_on_thread_creation",
        db_column_name="ping_on_thread_creation",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
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
        table_class_name="GuildConfigs",
        tablename="guild_configs",
        column_name="premium",
        db_column_name="premium",
        column_class_name="ForeignKey",
        column_class=ForeignKey,
        params={
            "references": PremiumGuildConfigs,
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="created_at",
        db_column_name="created_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="last_modified_at",
        db_column_name="last_modified_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="id",
        db_column_name="id",
        column_class_name="Serial",
        column_class=Serial,
        params={
            "null": False,
            "primary_key": True,
            "unique": True,
            "index": True,
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
        column_name="sID",
        db_column_name="sID",
        column_class_name="Varchar",
        column_class=Varchar,
        params={
            "length": 255,
            "default": generate_id,
            "null": False,
            "primary_key": False,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.hash,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="suggestion",
        db_column_name="suggestion",
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="guild_configuration",
        db_column_name="guild_configuration",
        column_class_name="ForeignKey",
        column_class=ForeignKey,
        params={
            "references": GuildConfigs,
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="user_configuration",
        db_column_name="user_configuration",
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
            "secret": True,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="state",
        db_column_name="state",
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
                "SuggestionStateEnum",
                {
                    "PENDING": "Pending",
                    "APPROVED": "Approved",
                    "REJECTED": "Rejected",
                    "CLEARED": "Cleared",
                },
            ),
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="moderator_note",
        db_column_name="moderator_note",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
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
        column_name="moderator_note_added_by",
        db_column_name="moderator_note_added_by",
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="moderator_note_added_by_display_text",
        db_column_name="moderator_note_added_by_display_text",
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="channel_id",
        db_column_name="channel_id",
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

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="message_id",
        db_column_name="message_id",
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

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="thread_id",
        db_column_name="thread_id",
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

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="resolved_by",
        db_column_name="resolved_by",
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
            "secret": True,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="resolved_by_display_text",
        db_column_name="resolved_by_display_text",
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="resolved_note",
        db_column_name="resolved_note",
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="resolved_at",
        db_column_name="resolved_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="image_url",
        db_column_name="image_url",
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
        table_class_name="Suggestions",
        tablename="suggestions",
        column_name="author_display_name",
        db_column_name="author_display_name",
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
        table_class_name="UserConfigs",
        tablename="user_configs",
        column_name="created_at",
        db_column_name="created_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": utc_now,
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
        table_class_name="UserConfigs",
        tablename="user_configs",
        column_name="last_modified_at",
        db_column_name="last_modified_at",
        column_class_name="Timestamptz",
        column_class=Timestamptz,
        params={
            "default": TimestamptzNow(),
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
        table_class_name="UserConfigs",
        tablename="user_configs",
        column_name="user_id",
        db_column_name="user_id",
        column_class_name="BigInt",
        column_class=BigInt,
        params={
            "default": 0,
            "null": False,
            "primary_key": True,
            "unique": True,
            "index": True,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    manager.add_column(
        table_class_name="UserConfigs",
        tablename="user_configs",
        column_name="dm_messages_disabled",
        db_column_name="dm_messages_disabled",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": False,
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
        table_class_name="UserConfigs",
        tablename="user_configs",
        column_name="ping_on_thread_creation",
        db_column_name="ping_on_thread_creation",
        column_class_name="Boolean",
        column_class=Boolean,
        params={
            "default": True,
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
