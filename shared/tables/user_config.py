from __future__ import annotations

from typing import TYPE_CHECKING
import hikari
from piccolo.table import Table
from piccolo.columns import BigInt, Boolean, Text

from shared.tables.mixins import AuditMixin

if TYPE_CHECKING:
    from shared.tables import PremiumUserConfigs


class UserConfigs(AuditMixin, Table):
    user_id = BigInt(
        unique=True,
        index=True,
        help_text="The discord user id",
    )
    generic_dm_messages_disabled = Boolean(
        default=False,
        help_text="If True, don't send this user dms for generic messages"
        " such as on suggestion create or resolution",
    )
    ping_on_thread_creation = Boolean(
        default=True,
        help_text="If True, ping this user when a thread is created for their suggestion",
    )
    primary_language_raw = Text(
        default=hikari.Locale.EN_GB.value,
        choices=hikari.Locale,
        help_text="The language to use when translating user messages. "
        "Defaults to ctx.interaction.locale when creating",
    )

    @property
    def primary_language(self) -> hikari.Locale:
        return hikari.Locale(self.primary_language_raw)

    async def fetch_premium_object(self) -> PremiumUserConfigs:
        """Fetch or create the associated premium user config."""
        from shared.tables import PremiumUserConfigs

        puc = await PremiumUserConfigs.objects().get(
            PremiumUserConfigs.user_config == self
        )
        if puc is not None:
            return puc

        puc = PremiumUserConfigs(user_config=self)
        await puc.save()
        return puc
