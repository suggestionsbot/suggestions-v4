from __future__ import annotations

from typing import TYPE_CHECKING

import hikari
from piccolo.columns import (
    Text,
    BigInt,
    ForeignKey,
    LazyTableReference,
    Serial,
    Timestamptz,
)
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from web.util import AuditMixin
from web.util.table_mixins import utc_now


class UserTokens(AuditMixin, Table):
    if TYPE_CHECKING:
        id: Serial

    subscription_id = Text(
        required=True,
        null=False,
        index=True,
        index_method=IndexMethod.hash,
        help_text="The Stripe id of the underlying subscription",
    )

    subscription_item_id = Text(
        required=True,
        null=False,
        index=True,
        index_method=IndexMethod.hash,
        help_text="The Stripe id of the underlying subscription item id from the invoice",
    )
    user_id = BigInt(
        index=True,
        required=True,
        null=False,
        help_text="The discord user id redeemed for this token",
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
    async def does_user_have_premium(cls, user_id: hikari.Snowflake | int) -> bool:
        return (
            await UserTokens.exists()
            .where(UserTokens.user_id == user_id)
            .where(utc_now() < UserTokens.expires_at)
        )

    async def invalidate(self) -> None:
        """Mark a token as expired and therefore not usable"""
        self.expires_at = utc_now()
        await self.save()
