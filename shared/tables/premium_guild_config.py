from datetime import timedelta
from enum import Enum

from piccolo.columns import Serial, Text, Integer, BigInt
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
    id = BigInt(
        primary_key=True,
        unique=True,
        index=True,
        help_text="The discord guild id",
    )
    suggestions_prefix = Text(
        default="",
        help_text="If the guild has premium, what to prefix suggestions with. "
        "Typically used for pinging roles.",
    )
    queued_suggestions_prefix = Text(
        default="",
        help_text="If the guild has premium, what to prefix queued suggestions with. "
        "Typically used for pinging roles.",
    )
    cooldown_period = Text(
        choices=CooldownPeriod,
        default=CooldownPeriod.Hour,
        help_text="Cooldown period for custom /suggest cooldown",
    )
    cooldown_amount = Integer(
        default=int((60 // 3) + 2),  # Mimic standard cooldown by default
        help_text="How many times during the period can /suggest be used?",
    )
