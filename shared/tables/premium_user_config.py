from typing import TYPE_CHECKING

from piccolo.columns import Serial, ForeignKey, LazyTableReference, Boolean
from piccolo.table import Table

from shared.tables.mixins import AuditMixin


class PremiumUserConfigs(AuditMixin, Table):
    if TYPE_CHECKING:
        id: Serial

    user_config = ForeignKey(
        LazyTableReference(
            table_class_name="UserConfigs",
            app_name="shared",
        ),
        index=True,
        null=False,
        required=True,
        unique=True,
    )
    wants_voting_notifications = Boolean(
        default=False,
        index=True,
        help_text="Wants notifications on resolved suggestions the user voted on.",
    )
