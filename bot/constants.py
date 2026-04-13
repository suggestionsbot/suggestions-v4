from __future__ import annotations

import os
import datetime
from datetime import timedelta
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

import hikari
import lightbulb
from commons import value_to_bool
from commons.caching import TimedCache
from dotenv import load_dotenv
from hikari import Color
from opentelemetry import trace

from bot.localisation import Localisation

if TYPE_CHECKING:
    from bot.utils import QueuedSuggestionsPaginator

load_dotenv()

VERSION = "4.0"
MAX_CONTENT_LENGTH = 1000
ERROR_COLOR = Color.of((214, 48, 49))
REJECTED_COLOR = Color.of((207, 0, 15))
APPROVED_COLOR = Color.of((0, 230, 64))
IMPLEMENTED_COLOR = Color.of((133, 222, 255))
DUPLICATE_COLOR = Color.of((200, 89, 255))
PENDING_COLOR = Color.of((255, 214, 99))
EMBED_COLOR = Color.of((255, 214, 99))
OTEL_TRACER = trace.get_tracer(__name__)
LOADED_AT = datetime.datetime.now(datetime.timezone.utc)  # Uptime calc
LOCALISATIONS = Localisation(
    base_path=Path("bot"),
)
PAGINATOR_OBJECTS: TimedCache[str, QueuedSuggestionsPaginator] = TimedCache(
    global_ttl=timedelta(minutes=15),
    lazy_eviction=False,
    ttl_from_last_access=True,
)
CONFIGURE_GROUP = lightbulb.Group(
    name="commands.configure.name",
    description="commands.configure.description",
    localize=True,
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
    contexts=[hikari.ApplicationContextType.GUILD],
)
NOTES_GROUP = lightbulb.Group(
    name="commands.note.name",
    description="commands.note.description",
    localize=True,
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
    contexts=[hikari.ApplicationContextType.GUILD],
)
BLOCKLIST_GROUP = lightbulb.Group(
    name="commands.blocklist.name",
    description="commands.blocklist.description",
    localize=True,
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
    contexts=[hikari.ApplicationContextType.GUILD],
)
QUEUE_GROUP = lightbulb.Group(
    name="commands.queue.name",
    description="commands.queue.description",
    localize=True,
    default_member_permissions=hikari.Permissions.MANAGE_GUILD,
    contexts=[hikari.ApplicationContextType.GUILD],
)

DEFAULT_UP_VOTE = hikari.CustomEmoji(
    id=(
        hikari.Snowflake(1470358301555294320)
        if value_to_bool(os.environ.get("DEBUG"))
        else hikari.Snowflake(1478974500057124864)
    ),
    name="nerdSuccess",
    is_animated=False,
)
DEFAULT_DOWN_VOTE = hikari.CustomEmoji(
    id=(
        hikari.Snowflake(1470358346879209503)
        if value_to_bool(os.environ.get("DEBUG"))
        else hikari.Snowflake(1478974532839800932)
    ),
    name="nerdError",
    is_animated=False,
)

# Clustering stuff
CLUSTER_ID = int(os.environ.get("CLUSTER_ID", 1))
TOTAL_SHARDS = int(os.environ.get("TOTAL_SHARDS", 1))
SHARDS_PER_CLUSTER = int(os.environ.get("SHARDS_PER_CLUSTER", 10))


class ErrorCode(IntEnum):
    SUGGESTION_MESSAGE_DELETED = 1
    MISSING_PERMISSIONS = 2
    MISSING_SUGGESTIONS_CHANNEL = 3
    MISSING_LOG_CHANNEL = 4
    SUGGESTION_NOT_FOUND = 5
    OWNER_ONLY = 6
    SUGGESTION_CONTENT_TOO_LONG = 7
    INVALID_GUILD_CONFIG_CHOICE = 8
    COMMAND_ON_COOLDOWN = 9
    GENERIC_FORBIDDEN = 10
    UNHANDLED_ERROR = 11
    GENERIC_NOT_FOUND = 12
    CONFIGURED_CHANNEL_NO_LONGER_EXISTS = 13
    MISSING_FETCH_PERMISSIONS_IN_SUGGESTIONS_CHANNEL = 14
    MISSING_FETCH_PERMISSIONS_IN_LOGS_CHANNEL = 15
    MISSING_TRANSLATION = 16
    SUGGESTION_RESOLUTION_ERROR = 17
    MISSING_SEND_PERMISSIONS_IN_SUGGESTION_CHANNEL = 18
    MISSING_THREAD_CREATE_PERMISSIONS = 19
    QUEUE_IMBALANCE = 20
    MISSING_QUEUE_CHANNEL = 21
    BLOCKLISTED_USER = 22
    MISSING_QUEUE_LOG_CHANNEL = 23
    MISSING_PERMISSIONS_IN_QUEUE_CHANNEL = 24
    INVALID_FILE_TYPE = 25

    @classmethod
    def from_value(cls, value: int) -> ErrorCode:
        return ErrorCode(value)
