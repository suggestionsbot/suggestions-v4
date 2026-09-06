import logging
from collections.abc import Sequence

import commons
import hikari
import lightbulb
from hikari.api import special_endpoints

from bot import utils
from bot.constants import LOCALISATIONS
from shared.tables import UserConfigs

log = logging.getLogger(__name__)


class UserPremiumMenu:
    @classmethod
    async def handle_interaction(  # noqa: PLR0912, PLR0911, PLR0915, C901
        cls,
        id_data: str,
        *,
        ctx: lightbulb.components.MenuContext,
        event: hikari.ComponentInteractionCreateEvent,
        user_config: UserConfigs,
    ) -> None:
        if not await user_config.premium_is_enabled():
            await ctx.respond(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=LOCALISATIONS.get_localized_string(
                            "menus.user_configuration.premium_menu.responses.premium_required",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.LinkButtonBuilder(
                                url="https://dashboard.suggestions.gg/stripe/users/checkout",
                                label=LOCALISATIONS.get_localized_string(
                                    "menus.user_configuration.premium_menu.responses.premium_required.link",
                                    user_config.primary_language,
                                ),
                            ),
                        ],
                    ),
                ],
                ephemeral=True,
            )
            return

        await ctx.defer(ephemeral=True)

        event_values: Sequence[str] = event.interaction.values
        premium_config = await user_config.fetch_premium_object()
        if id_data == "premium_receive_notif_for_votes":
            result = commons.value_to_bool(event_values[0])
            premium_config.wants_voting_notifications = result
            await premium_config.save()

            key = (
                "menus.user_configuration.premium_menu.responses.will_notify"
                if result
                else "menus.user_configuration.premium_menu.responses.will_not_notify"
            )
            await ctx.respond(
                LOCALISATIONS.get_localized_string(key, user_config.primary_language),
                ephemeral=True,
            )

    @classmethod
    async def build_premium_components(
        cls,
        *,
        user_config: UserConfigs,
        link_id: str | None = None,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        # Currently is embedded within base page, but exists here to
        # more easily expand to its own page later.
        if link_id is None:
            link_id = await utils.otel.generate_trace_link_state()

        premium_config = await user_config.fetch_premium_object()
        components: list[special_endpoints.ComponentBuilder] = [
            hikari.impl.TextDisplayComponentBuilder(
                content=LOCALISATIONS.get_localized_string(
                    "menus.user_configuration.premium_menu.overall_description",
                    user_config.primary_language,
                ),
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=LOCALISATIONS.get_localized_string(
                            "menus.user_configuration.premium_menu.premium_receive_notif_for_votes",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"ucm:{link_id}:premium_receive_notif_for_votes",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=LOCALISATIONS.get_localized_string(
                                            "menus.user_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=premium_config.wants_voting_notifications,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=LOCALISATIONS.get_localized_string(
                                            "menus.user_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not premium_config.wants_voting_notifications,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                ]
            ),
        ]
        return components
