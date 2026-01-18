from __future__ import annotations

import typing
from typing import TYPE_CHECKING

from piccolo.columns import (
    Text,
    BigInt,
    ForeignKey,
    LazyTableReference,
    Serial,
    Boolean,
    Timestamptz,
)
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from web.util import AuditMixin
from web.util.table_mixins import utc_now

if typing.TYPE_CHECKING:
    from web.tables import Users


class GuildTokens(AuditMixin, Table):
    if TYPE_CHECKING:
        id: Serial

    subscription_id = Text(
        required=True,
        null=False,
        index=True,
        secret=True,
        index_method=IndexMethod.hash,
        help_text="The Stripe id of the underlying subscription",
    )
    used_for_guild = BigInt(
        index=True,
        default=None,
        null=True,
        help_text="The discord guild id redeemed for this token",
    )
    user = ForeignKey(
        LazyTableReference("Users", module_path="web.tables"),
        index=True,
        help_text="The user who owns this token",
    )
    # Subscription length + 5 days
    expires_at = Timestamptz(
        null=False,
        help_text="When this token expires according to the underlying subscription.",
    )

    @classmethod
    async def does_guild_have_premium(cls, guild_id: int):
        return (
            await GuildTokens.exists()
            .where(GuildTokens.used_for_guild == guild_id)
            .where(utc_now() < GuildTokens.expires_at)
        )

    @classmethod
    async def get_unused_token_count(cls, user: Users):
        return (
            await GuildTokens.count()
            .where(GuildTokens.user == user)
            .where(utc_now() < GuildTokens.expires_at)
            .where(GuildTokens.used_for_guild.is_null())
        )

    async def invalidate(self):
        """Mark a token as expired and therefore not usable"""
        self.expires_at = utc_now()
        await self.save()
