import datetime

from piccolo.columns import Timestamptz


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class AuditMixin:
    created_at = Timestamptz(
        default=utc_now,
        help_text="When this object was created.",
    )
    last_modified_at = Timestamptz(
        auto_update=utc_now,
        help_text="When this objected was last updated.",
    )
