from enum import StrEnum
from typing import TYPE_CHECKING, Self

from piccolo.columns import Timestamptz, Serial, Text, BigInt
from piccolo.table import Table

from shared.tables import GuildConfigs, UserConfigs
from shared.tables.mixins.audit import utc_now


class CommandTypes(StrEnum):
    SLASH_COMMAND = "Slash Command"
    MESSAGE_COMMAND = "Message Command"
    BUTTON = "Button"
    OTHER = "Other"


# We don't track success states as that is too complicated
# All we care about is whether or not something did get invoked
class CommandInvokes(Table):
    if TYPE_CHECKING:
        id: Serial

    action = Text(help_text="The action ran", required=True)
    action_type = Text(
        help_text="The type of action",
        choices=CommandTypes,
        required=True,
    )
    created_at = Timestamptz(
        default=utc_now,
        help_text="When this object was created.",
        index=True,
    )
    user_locale = Text(help_text="The user locale used in the command")
    guild_locale = Text(
        help_text="The guild locale used in the command",
        null=True,
        default=None,
    )
    user_id = BigInt(help_text="The user who triggered the command")
    guild_id = BigInt(
        help_text="The guild where the command was triggered",
        null=True,
        default=None,
    )

    @classmethod
    async def create(
        cls,
        *,
        user_config: UserConfigs,
        action: str,
        command_type: CommandTypes,
        guild_config: GuildConfigs | None = None,
    ) -> Self:
        obj = cls(
            action=action,
            action_type=command_type,
            user_id=user_config.user_id,
            user_locale=user_config.primary_language.value,
            guild_id=guild_config.guild_id if guild_config else None,
            guild_locale=guild_config.primary_language.value if guild_config else None,
        )
        await obj.save()
        return obj
