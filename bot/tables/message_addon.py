import random
import typing
from enum import Enum
from typing import TYPE_CHECKING

import arrow
from piccolo.columns import Serial, Text, BigInt, Timestamptz, ForeignKey
from piccolo.table import Table

from shared.tables import UserConfigs
from shared.tables.mixins import AuditMixin
from shared.tables.mixins.audit import utc_now


class PossibleMessageAddons(str, Enum):
    READ_CHANGELOG = "message_addons.read_changelog"
    PRODUCT_UPDATES = "message_addons.product_updates"


GLOBAL_MESSAGES: list[PossibleMessageAddons] = [
    PossibleMessageAddons.READ_CHANGELOG,
    PossibleMessageAddons.PRODUCT_UPDATES,
]
"""Messages we can add to any situation"""


class MessageAddons(Table):
    if TYPE_CHECKING:
        id: Serial

    shown_message = Text(
        help_text="The message a user was shown",
        choices=PossibleMessageAddons,
        required=True,
        null=False,
    )
    user = ForeignKey(UserConfigs, index=True)
    shown_at = Timestamptz(
        default=utc_now, help_text="When this message was shown to the user", index=True
    )

    @property
    def shown_message_enum(self) -> PossibleMessageAddons:
        return PossibleMessageAddons(self.shown_message)

    @classmethod
    async def has_been_shown_message_recently(cls, user: UserConfigs) -> bool:
        """Has the user been shown a message recently already"""
        recent_period = arrow.get(utc_now()).shift(months=-2).datetime
        return (
            await MessageAddons.exists()
            .where(MessageAddons.user == user)
            .where(recent_period < MessageAddons.shown_at)
            .run()
        )

    @classmethod
    async def get_message(
        cls, user: UserConfigs, *, hint: PossibleMessageAddons | None = None
    ) -> typing.Self | None:
        """Get a message to add if the user hasn't seen one recently"""
        if await cls.has_been_shown_message_recently(user):
            return None

        # We can create one for usage
        if hint is None:
            hint = random.choice(GLOBAL_MESSAGES)

        ma = cls(
            shown_message=hint,
            user=user,
        )
        await ma.save()
        return ma
