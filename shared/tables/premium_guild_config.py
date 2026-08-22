from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING

from piccolo.columns import Text, Integer, BigInt, Serial
from piccolo.table import Table

from shared.tables.mixins import AuditMixin


class CooldownPeriod(str, Enum):
    Hour = "Hour"
    Day = "Day"
    Week = "Week"
    Fortnight = "Fortnight"
    Month = "Month"

    def as_timedelta(self) -> timedelta:
        if self is self.Hour:
            return timedelta(hours=1)
        elif self is self.Day:
            return timedelta(days=1)
        elif self is self.Week:
            return timedelta(weeks=1)
        elif self is self.Fortnight:
            return timedelta(weeks=2)
        elif self is self.Month:
            return timedelta(weeks=4)
        else:
            raise NotImplementedError


class PremiumGuildConfigs(AuditMixin, Table):
    if TYPE_CHECKING:
        id: Serial

    guild_id = BigInt(
        unique=True,
        index=True,
        help_text="The discord guild id",
    )
    suggestions_prefix = Text(
        default=None,
        null=True,
        help_text="If the guild has premium, what to prefix suggestions with. "
        "Typically used for pinging roles.",
    )
    queued_suggestions_prefix = Text(
        default=None,
        null=True,
        help_text="If the guild has premium, what to prefix queued suggestions with. "
        "Typically used for pinging roles.",
    )
    suggestion_button_message_prefix = Text(
        default=None,
        null=True,
        help_text="What to send alongside the physical create suggestion button.",
    )
    suggestion_button_message = Text(
        default=None,
        null=True,
        help_text="What to send as the the physical create suggestion button.",
    )
    cooldown_period = Text(
        choices=CooldownPeriod,
        default=CooldownPeriod.Hour,
        help_text="Cooldown period for custom /suggest cooldown",
    )
    cooldown_amount = Integer(
        default=None,
        null=True,
        help_text="How many times during the period can /suggest be used?",
    )
