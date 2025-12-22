from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from piccolo.columns import (
    UUID,
    ForeignKey,
    Text,
    Serial,
    LazyTableReference,
    Boolean,
    Timestamptz,
)
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from web.util import AuditMixin

if TYPE_CHECKING:
    from web.tables import Users


class AlertLevels(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"

    @classmethod
    def from_str(cls, level) -> AlertLevels:
        return cls[level.upper()]


class Alerts(AuditMixin, Table):
    id: Serial
    uuid = UUID(default=uuid.uuid4, index=True, index_method=IndexMethod.hash)
    target = ForeignKey(
        LazyTableReference("Users", module_path="web.tables"),
        index=True,
        help_text="Who should be notified?",
        null=False,
    )
    message = Text(help_text="The text to show the target on next request?")
    level = Text(help_text="The level to show it at", choices=AlertLevels)
    has_been_shown = Boolean(
        default=False, help_text="Whether the user has seen the alert?"
    )
    was_shown_at = Timestamptz(
        null=True,
        default=None,
        required=False,
        help_text="When this user saw the alert.",
    )

    @classmethod
    async def create_alert(
        cls, user: Users, message: str, level: AlertLevels
    ) -> Alerts:
        notif = Alerts(
            target=user,
            message=message,
            level=level,
        )
        await notif.save()
        return notif
