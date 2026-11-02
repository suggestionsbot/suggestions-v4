from __future__ import annotations

from typing import Self, TYPE_CHECKING

from piccolo.columns import (
    Serial,
    ForeignKey,
    BigInt,
    LazyTableReference,
    OnDelete,
)
from piccolo.table import Table

from shared.tables.mixins import AuditMixin

if TYPE_CHECKING:
    from shared.tables import GuildConfigs


class SuggestionButtons(Table, AuditMixin):
    id = Serial(
        primary_key=True,
        unique=True,
        index=True,
    )
    guild_configuration = ForeignKey(
        LazyTableReference(
            table_class_name="GuildConfigs",
            app_name="shared",
        ),
        index=True,
        on_delete=OnDelete.restrict,
    )
    channel_id = BigInt(index=True, help_text="The channel this button is in")
    message_id = BigInt(help_text="The message id of the button")

    @classmethod
    async def fetch_buttons_for_channel(
        cls, *, channel_id: int, guild_configuration: GuildConfigs | int
    ) -> list[Self]:
        query = (
            cls.objects()
            .where(cls.channel_id == channel_id)
            .where(cls.guild_configuration == guild_configuration)
        )

        return await query

    @classmethod
    async def create_new(
        cls, *, guild_config: GuildConfigs, channel_id: int, message_id: int
    ) -> Self:
        """Create a new entry."""
        obj = cls(
            guild_configuration=guild_config, channel_id=channel_id, message_id=message_id
        )
        await obj.save()
        return obj
