from piccolo.table import Table
from piccolo.columns import BigInt, Boolean

from shared.tables.mixins import AuditMixin


class UserConfigs(AuditMixin, Table):
    user_id = BigInt(
        unique=True,
        index=True,
        help_text="The discord user id",
    )
    dm_messages_disabled = Boolean(
        default=False, help_text="If True, don't send this user DM's"
    )
    ping_on_thread_creation = Boolean(
        default=True,
        help_text="If True, ping this user when a thread is created for their suggestion",
    )
