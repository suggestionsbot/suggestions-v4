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

    def __eq__(self, other) -> bool:
        return isinstance(other, self.__class__) and getattr(
            self, self._meta.primary_key._meta.name, None
        ) == getattr(other, other._meta.primary_key._meta.name, None)
