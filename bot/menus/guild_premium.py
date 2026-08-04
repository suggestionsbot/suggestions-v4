import logging
from collections.abc import Sequence

import hikari
import lightbulb
from hikari.api import special_endpoints
from hikari.interactions.interaction_components import (
    TextInputInteractionComponent,
    TextSelectMenuInteractionComponent,
)

from bot import utils
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs

log = logging.getLogger(__name__)


class GuildPremiumMenu:
    @staticmethod
    def extract_value(event: hikari.ModalInteractionCreateEvent, value_name: str):
        for entry in event.interaction.components:
            if entry.component.custom_id == value_name:
                return (
                    entry.component.value
                    if isinstance(entry.component, TextInputInteractionComponent)
                    else entry.component.values[0]
                    if isinstance(entry.component, TextSelectMenuInteractionComponent)
                    else None
                )
        return None

    @classmethod
    async def handle_modal_interaction(  # noqa: PLR0912, PLR0911, PLR0915, C901
        cls,
        id_data: str,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        event: hikari.ModalInteractionCreateEvent,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if id_data == "custom_name":
            await ctx.client.rest.edit_my_member(
                guild_config.guild_id, nickname=cls.extract_value(event, "name")
            )
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.changed_name",
                    user_config.primary_language,
                )
            )

    @classmethod
    async def handle_interaction(  # noqa: PLR0912, PLR0911, PLR0915, C901
        cls,
        id_data: str,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        event: hikari.ComponentInteractionCreateEvent,
        link_id: str,
        user_config: UserConfigs,
        guild_config: GuildConfigs,
    ) -> None:
        if not await guild_config.premium_is_enabled():
            await ctx.respond(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.premium_menu.responses.premium_required",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.LinkButtonBuilder(
                                url="https://dashboard.suggestions.gg/stripe/guilds/checkout",
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.responses.premium_required.link",
                                    user_config.primary_language,
                                ),
                            ),
                        ],
                    ),
                ],
                ephemeral=True,
            )
            return

        # Modals first
        if id_data == "premium_modal_custom_name":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_name.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:custom_name",
                components=await cls.build_name_modal(localisations, user_config),
            )

        await ctx.defer(ephemeral=True)

    @classmethod
    async def build_name_modal(
        cls, localisations: Localisation, user_config: UserConfigs
    ):
        return [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_name.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_name.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="name",
                    style=hikari.TextInputStyle.SHORT,
                    required=False,
                    min_length=1,
                    max_length=32,
                ),
            ),
        ]

    @classmethod
    async def build_premium_components(
        cls,
        *,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        link_id: str | None = None,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        if link_id is None:
            link_id = await utils.otel.generate_trace_link_state()

        components: list[special_endpoints.ComponentBuilder] = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.guild_configuration.base_menu.overall_description",
                    user_config.primary_language,
                ),
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.premium_menu.custom_details",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label="Edit Name",
                                custom_id=f"gcm:{link_id}:premium_modal_custom_name",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label="Edit Avatar",
                                custom_id=f"gcm:{link_id}:premium_modal_custom_avatar",
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.premium_menu.suggestion_prefix",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label="Edit Suggestion Message",
                                custom_id=f"gcm:{link_id}:premium_modal_suggestion_prefix",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label="Edit Queued Suggestion Message",
                                custom_id=f"gcm:{link_id}:premium_modal_queued_suggestion_prefix",
                            ),
                        ],
                    ),
                ],
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.PRIMARY,
                        label=localisations.get_localized_string(
                            "menus.guild_configuration.responses.pagination.view_settings",
                            user_config.primary_language,
                        ),
                        custom_id=f"gcm:{link_id}:view_page_1",
                    ),
                ],
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/guild-configuration",
                        label=localisations.get_localized_string(
                            "menus.guild_configuration.view_docs",
                            user_config.primary_language,
                        ),
                    ),
                ],
            ),
        ]

        # Pagination

        # Docs for extra info

        return components
