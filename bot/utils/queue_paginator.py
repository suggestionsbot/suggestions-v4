from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import hikari
import lightbulb
from hikari.api import (
    ContainerComponentBuilder,
    MessageActionRowBuilder,
    TextDisplayComponentBuilder,
)

from bot.constants import LOCALISATIONS
from bot.exceptions import QueueImbalance

if TYPE_CHECKING:
    from shared.tables import QueuedSuggestions

log = logging.getLogger(__name__)


class QueuedSuggestionsPaginator:
    def __init__(
        self,
        *,
        data,
        ctx: lightbulb.Context,
        locale: hikari.Locale,
        pid: str,
        link_id: str,
    ):
        self._current_page_index = 0
        self._paged_data: list[str] = data
        self._guild_id: int = ctx.guild_id
        self._rest = ctx.interaction.app.rest
        self._locale: hikari.Locale = locale
        self._pid: str = pid
        self._link_id: str = link_id
        self.original_interaction: hikari.CommandInteraction = ctx.interaction

    @property
    def current_page(self) -> int:
        """The current page for this paginator."""
        return self._current_page_index + 1

    @current_page.setter
    def current_page(self, value) -> None:
        # Wrap around
        if value > self.total_pages:
            self._current_page_index = 0
        elif value <= 0:
            self._current_page_index = self.total_pages - 1
        else:
            self._current_page_index = value - 1

    @property
    def total_pages(self) -> int:
        """How many pages exist in this paginator."""
        return len(self._paged_data)

    @property
    def pages(self) -> list[str]:
        return self._paged_data

    async def remove_current_page(self):
        wrap = self.current_page == self.total_pages
        self._paged_data.pop(self._current_page_index)
        if wrap:
            self.current_page = 1

        if self.total_pages == 0:
            await self.original_interaction.edit_initial_response(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=LOCALISATIONS.get_localized_string(
                            "menus.queue_paginator.responses.expired",
                            self._locale,
                        ),
                    ),
                ],
            )

        else:
            await self.original_interaction.edit_initial_response(
                components=await self.format_page()
            )

        return None

    async def get_current_queued_suggestion(self) -> QueuedSuggestions:
        from shared.tables import QueuedSuggestions, QueuedSuggestionStateEnum

        qs: QueuedSuggestions | None = await QueuedSuggestions.fetch_queued_suggestion(
            self._paged_data[self._current_page_index], self._guild_id
        )
        if qs.state != QueuedSuggestionStateEnum.PENDING:
            raise QueueImbalance

        return qs

    async def format_page(
        self,
    ) -> (
        list[
            ContainerComponentBuilder
            | MessageActionRowBuilder
            | TextDisplayComponentBuilder
        ]
        | None
    ):
        try:
            suggestion: QueuedSuggestions = await self.get_current_queued_suggestion()
        except QueueImbalance:
            await self.remove_current_page()
            log.warning(
                "Hit QueueImbalance",
                extra={
                    "interaction.author.id": self.original_interaction.user.id,
                    "interaction.author.global_name": self.original_interaction.user.global_name,
                    "interaction.guild.id": self.original_interaction.guild_id,
                },
            )
        else:
            components: list[
                ContainerComponentBuilder
                | MessageActionRowBuilder
                | TextDisplayComponentBuilder
            ] = [
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "menus.queue_paginator.responses.page.footer",
                        self._locale,
                        extras={"CURRENT": self.current_page, "TOTAL": self.total_pages},
                    )
                ),
            ]
            qsc = await suggestion.as_components(
                rest=self._rest,
                localisations=LOCALISATIONS,
                locale=self._locale,
                paginator_id=self._pid,
                link_id=self._link_id,
            )
            components.extend(qsc)
            components.extend(
                [
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                emoji="\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f",
                                custom_id=f"v4_queue:back:{self._pid}::{self._link_id}",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                emoji="\N{BLACK SQUARE FOR STOP}\ufe0f",
                                custom_id=f"v4_queue:stop:{self._pid}::{self._link_id}",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f",
                                custom_id=f"v4_queue:next:{self._pid}::{self._link_id}",
                            ),
                        ]
                    ),
                ]
            )
            return components

    async def update_message_with_current_page(self):
        await self.original_interaction.edit_initial_response(
            components=await self.format_page()
        )

    async def stop_paginating(self):
        await self.original_interaction.edit_initial_response(
            components=[
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "menus.queue_paginator.responses.expired",
                        self._locale,
                    ),
                ),
            ],
        )
