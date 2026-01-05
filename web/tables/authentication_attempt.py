from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import arrow
from piccolo.columns import (
    Serial,
    ForeignKey,
    LazyTableReference,
    Timestamptz,
    Text,
    Or,
)
from piccolo.table import Table

from web.util.table_mixins import utc_now, AuditMixin
from web.tables import Users


class AuthenticationAttempts(
    AuditMixin,
    Table,
    help_text="Logs authentication attempts against legitimate accounts",
):
    if TYPE_CHECKING:
        id: Serial

    user = ForeignKey(
        LazyTableReference("Users", module_path="web.tables"),
        null=False,
        index=True,
        required=True,
    )
    attempt_made_at = Timestamptz(
        null=False,
        required=True,
        help_text="When this attempt was made.",
    )
    attempt_made_via = Text(help_text="What auth provider called this", null=False, required=True)

    @classmethod
    async def create_via_email(cls, email: str, provider: str) -> None:
        """Creates an authentication attempt for a given email.

        Notes
        -----
        Does nothing if a user with that email doesn't exist
        """
        user = await Users.objects().get(Users.email == email)  # type: ignore
        if not user:
            return None

        aa = AuthenticationAttempts(
            user=user,
            attempt_made_at=utc_now(),
            attempt_made_via=provider,
        )
        await aa.save()
        return None

    @classmethod
    async def create_via_username(cls, username: str, provider: str) -> None:
        """Creates an authentication attempt for a given username.

        Notes
        -----
        Does nothing if a user with that email doesn't exist
        """
        user = await Users.objects().get(Users.username == username)  # type: ignore
        if not user:
            return None

        aa = AuthenticationAttempts(
            user=user,
            attempt_made_at=utc_now(),
            attempt_made_via=provider,
        )
        await aa.save()
        return None

    @classmethod
    async def has_exceeded_limits(cls, user_detail: str, limit: int, period: timedelta) -> bool:
        """Return true if user has more attempts made during period then limit allows"""
        from_time = arrow.get(utc_now()).shift(seconds=(period.total_seconds() * -1)).datetime
        count = (
            await AuthenticationAttempts.count()
            .where(
                Or(
                    AuthenticationAttempts.user.email == user_detail,  # type: ignore
                    AuthenticationAttempts.user.username == user_detail,  # type: ignore
                )
            )
            .where(AuthenticationAttempts.attempt_made_at >= from_time)
        )
        return count >= limit
