from __future__ import annotations

import datetime
import secrets
from typing import TYPE_CHECKING, cast

import arrow
import commons.timing
from piccolo.columns import Serial, Varchar, ForeignKey, LazyTableReference, Timestamptz
from piccolo.table import Table

from web.tables import Users
from web.util import AuditMixin
from web.util.table_mixins import utc_now


class APIToken(AuditMixin, Table, tablename="api_token"):
    if TYPE_CHECKING:
        id: Serial

    token = Varchar(
        length=100,
        null=False,
        help_text="A given users API token",
        secret=True,
    )
    user = ForeignKey(
        LazyTableReference("Users", module_path="web.tables"),
        index=True,
    )
    expiry_date: Timestamptz = Timestamptz(
        null=False,
        help_text="When this API token expires",
    )

    #: We set a hard limit on the expiry date - it can keep on getting extended
    #: up until this value, after which it's best to invalidate it, and either
    #: require login again, or just create a new session token.
    max_expiry_date: Timestamptz = Timestamptz(
        null=False,
        help_text="The maximum time until that this API token can be extended until",
    )

    @classmethod
    async def create_api_token(
        cls,
        user: Users,
        expiry_date: datetime.timedelta,
        max_expiry_date: datetime.timedelta,
    ) -> APIToken:
        while True:
            token = secrets.token_hex(nbytes=32)
            if not await cls.exists().where(cls.token == token).run():
                break

        session = cls(
            token=token,
            user=user,
            expiry_date=arrow.get(utc_now()).shift(seconds=expiry_date.total_seconds()).datetime,
            max_expiry_date=arrow.get(utc_now())
            .shift(seconds=max_expiry_date.total_seconds())
            .datetime,
        )
        await session.save().run()
        return session

    async def token_expires_within_window(self, increase_window: datetime.timedelta) -> bool:
        """Returns true if the token cannot be increased by window without expiring."""
        return commons.timing.is_within_next_(
            self.expiry_date, self.max_expiry_date, increase_window
        )

    @classmethod
    async def validate_token_is_valid(cls, token: str) -> bool:
        """Return true if the provided token is still valid"""
        return await cls.exists().where(cls.token == token).where(utc_now() < cls.expiry_date).run()

    @classmethod
    async def get_instance_from_token(cls, token) -> APIToken | None:
        return await cls.objects(cls.user).where(cls.token == token).first().run()

    @classmethod
    async def get_token(
        cls,
        token: str,
        *,
        expiry_window: datetime.timedelta,
        max_expiry_window: datetime.timedelta,
        increase_window: datetime.timedelta | None = None,
    ) -> APIToken | None:
        """Returns an API token for usage, increasing the expiry by the provided amount.

        Returns
        -------
        APIToken
            The relevant APIToken Row
        None
            The provided token was expired

        Notes
        -----
        If the current token would expire during increase,
        a new token and row is returned instead.
        """
        api_token = await cls.get_instance_from_token(token)

        if commons.timing.is_in_the_past(
            utc_now(),
            cast(datetime.datetime, cast(object, api_token.expiry_date)),
        ):
            # Token has already expired
            return None

        if increase_window is None:
            # Token is not expired,
            # and we don't want to expand its validity
            return api_token

        if not await api_token.token_expires_within_window(increase_window):
            # Token is fine to expand
            api_token.expiry_date = (
                cast(datetime.datetime, cast(object, api_token.expiry_date)) + increase_window
            )
            await api_token.save()
            return api_token

        # Delete token and issue new one as it would put the new
        # expiry time past the max valid window
        await cls.delete_token(cast(str, cast(object, api_token.token)))
        return await cls.create_api_token(
            cast(Users, cast(object, api_token.user)),
            expiry_window,
            max_expiry_window,
        )

    @classmethod
    async def delete_token(cls, token: str):
        await cls.delete().where(cls.token == token).run()
