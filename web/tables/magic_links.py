import secrets
from typing import TYPE_CHECKING

from commons import timing
from piccolo.columns import Boolean, Serial, Text, Timestamptz
from piccolo.columns.indexes import IndexMethod
from piccolo.columns.readable import Readable
from piccolo.table import Table

from web import constants
from web.util.table_mixins import utc_now, AuditMixin


class MagicLinks(AuditMixin, Table):
    if TYPE_CHECKING:
        id: Serial

    email = Text(null=False, help_text="The email this link was sent to")
    token = Text(
        null=False,
        index=True,
        index_method=IndexMethod.hash,
        help_text="The token included in the sent email",
        secret=True,
    )
    cookie = Text(
        null=False,
        secret=True,
        help_text="The cookie value set in the browser that made the request",
    )
    used_in_same_request_browser = Boolean(
        null=True,
        required=False,
        default=None,
        help_text="Did the user accept the link in the same browser that requested it?",
    )
    created_at = Timestamptz(
        default=utc_now,
        help_text="When this link was created.",
    )
    used_at = Timestamptz(
        null=True,
        default=None,
        required=False,
        help_text="When this link was used.",
    )

    @classmethod
    def get_readable(cls) -> Readable:
        return Readable(template="%s", columns=[cls.email])

    @property
    def is_still_valid(self) -> bool:
        """Returns True if the link is still valid"""
        return timing.is_within_next_(
            self.created_at, utc_now(), constants.MAGIC_LINK_VALIDITY_WINDOW
        )

    @staticmethod
    def generate_token() -> str:
        return secrets.token_hex(32)
