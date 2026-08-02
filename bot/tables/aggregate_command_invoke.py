from typing import TYPE_CHECKING

from piccolo.columns import Timestamptz, Serial, JSON, Integer, JSONB
from piccolo.table import Table

from shared.tables.mixins.audit import utc_now


class AggregateCommandInvokes(Table, help_text="A week by week view of command data."):
    if TYPE_CHECKING:
        id: Serial

    total_users_seen = Integer()
    total_guilds_seen = Integer()
    total_voters_seen = Integer()
    total_users_who_only_voted = Integer()
    actions = JSONB()
    action_types = JSONB()
    user_locales = JSONB()
    guild_locales = JSONB()
    raw_data = JSONB(help_text="The raw data used to compute the above statistics.")
    created_at = Timestamptz(
        default=utc_now, help_text="When this object was created.", index=True
    )
    data_for_week_starting = Timestamptz(
        help_text="The week this data relates to", index=True
    )
