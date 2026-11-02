from __future__ import annotations

from typing import Self, TYPE_CHECKING, Any

import hikari
from piccolo.columns import (
    Serial,
    ForeignKey,
    BigInt,
    LazyTableReference,
    OnDelete,
    Boolean,
    Text,
)
from piccolo.table import Table

from bot.constants import LOCALISATIONS
from shared.tables.mixins import AuditMixin

if TYPE_CHECKING:
    from shared.tables import GuildConfigs


class SuggestionButtons(Table, AuditMixin):
    id = Serial(
        primary_key=True,
        unique=True,
        index=True,
    )
    guild_configuration = ForeignKey(
        LazyTableReference(
            table_class_name="GuildConfigs",
            app_name="shared",
        ),
        index=True,
        on_delete=OnDelete.restrict,
    )
    channel_id = BigInt(index=True, help_text="The channel this button is in")
    message_id = BigInt(help_text="The message id of the button")

    message_prefix = Text(
        default=None,
        null=True,
        help_text="What to send alongside the physical create suggestion button.",
    )
    hide_message = Boolean(
        default=False,
        help_text="Should the sent messages only be the button?",
    )
    button_message = Text(
        default=None,
        null=True,
        help_text="What to send as the the physical create suggestion button.",
    )
    button_is_sticky = Boolean(
        default=False,
        help_text="Should the button message be re-sent when it's no"
        " longer at the button of the channel?",
    )

    async def build_suggestion_button(self, guild_config: GuildConfigs) -> list[Any]:
        """Build and return the suggestion button components."""
        message: str | None = self.message_prefix
        button_message: str | None = self.button_message
        if message is None:
            message: str = LOCALISATIONS.get_localized_string(
                "menus.guild_configuration.responses.sent_suggestions_button.description",
                guild_config.primary_language,
            )

        if button_message is None:
            button_message = LOCALISATIONS.get_localized_string(
                "menus.guild_configuration.responses.sent_suggestions_button.button",
                guild_config.primary_language,
            )

        components = []
        if not self.hide_message:
            components.append(hikari.impl.TextDisplayComponentBuilder(content=message))

        components.append(
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.PRIMARY,
                        label=button_message,
                        custom_id="v4_suggest_button",
                    ),
                ],
            )
        )
        return components

    @classmethod
    async def fetch_sticky_buttons_for_channel(
        cls, *, channel_id: int, guild_configuration: GuildConfigs | int
    ) -> list[Self]:
        query = (
            cls.objects()
            .where(cls.channel_id == channel_id)
            .where(cls.guild_configuration == guild_configuration)
            .where(cls.button_is_sticky.eq(value=True))
        )

        return await query

    @classmethod
    async def create_new(
        cls,
        *,
        guild_config: GuildConfigs,
        channel_id: int,
        message_id: int,
        message_prefix: str | None = None,
        hide_message: bool = False,
        button_message: str | None = None,
        button_is_sticky: bool = False,
    ) -> Self:
        """Create a new entry."""
        obj = cls(
            guild_configuration=guild_config,
            channel_id=channel_id,
            message_id=message_id,
            message_prefix=message_prefix,
            hide_message=hide_message,
            button_message=button_message,
            button_is_sticky=button_is_sticky,
        )
        await obj.save()
        return obj
