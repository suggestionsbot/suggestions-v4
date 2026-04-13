from typing import Literal

import hikari
import lightbulb
from commons.caching import NonExistentEntry

from bot import utils
from bot.constants import PAGINATOR_OBJECTS
from bot.localisation import Localisation
from bot.menus import SuggestionsQueueMenu
from shared.tables import (
    UserConfigs,
)
from shared.utils import configs


class SuggestionsQueueViewerMenu:
    @classmethod
    async def handle_paginator_interaction(
        cls,
        queue_id: str,
        action: Literal["back", "next", "stop", "approve", "reject"],
        queued_suggestion_id: str | None = None,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        event: hikari.ComponentInteractionCreateEvent,
    ):
        await ctx.defer(ephemeral=True)
        user_config: UserConfigs = await configs.ensure_user_config(
            user_id=event.interaction.user.id, locale=event.interaction.locale
        )
        guild_config = await configs.ensure_guild_config(ctx.guild_id)
        try:
            paginator = PAGINATOR_OBJECTS.get_entry(queue_id)
        except NonExistentEntry:
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.queue_paginator.responses.expired",
                    user_config.primary_language,
                )
            )
            return

        if action == "back":
            paginator.current_page -= 1
            await paginator.update_message_with_current_page()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.queue_paginator.responses.back",
                    user_config.primary_language,
                )
            )
            return

        elif action == "next":
            paginator.current_page += 1
            await paginator.update_message_with_current_page()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.queue_paginator.responses.next",
                    user_config.primary_language,
                )
            )
            return

        elif action == "stop":
            PAGINATOR_OBJECTS.delete_entry(queue_id)
            await paginator.stop_paginating()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.queue_paginator.responses.cancelled",
                    user_config.primary_language,
                )
            )
            return

        elif action == "approve":
            if queued_suggestion_id not in paginator.pages:
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.queue_paginator.responses.already_resolved",
                        user_config.primary_language,
                    )
                )
                return

            await paginator.remove_current_page()
            await SuggestionsQueueMenu.handle_physical_interaction(
                queued_suggestion_id,
                to_approve=True,
                ctx=ctx,
                localisations=localisations,
                guild_config=guild_config,
                event=event,
            )
            return

        elif action == "reject":
            if queued_suggestion_id not in paginator.pages:
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.queue_paginator.responses.already_resolved",
                        user_config.primary_language,
                    )
                )
                return

            await paginator.remove_current_page()
            await SuggestionsQueueMenu.handle_physical_interaction(
                queued_suggestion_id,
                to_approve=False,
                ctx=ctx,
                localisations=localisations,
                guild_config=guild_config,
                event=event,
            )
            return

        await ctx.respond(
            embed=utils.error_embed(
                "Something went wrong.", "Please contact support if this keeps happening."
            )
        )
