import logging
from collections.abc import Sequence
from typing import cast

import hikari
import lightbulb
from hikari.api import special_endpoints
from hikari.interactions.interaction_components import (
    TextInputInteractionComponent,
    TextSelectMenuInteractionComponent,
    FileUploadInteractionComponent,
)

from bot import utils
from bot.constants import ENABLE_CUSTOM_NAME_AND_AVATARS
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs

log = logging.getLogger(__name__)


class GuildPremiumMenu:
    @staticmethod
    def extract_value(
        event: hikari.ModalInteractionCreateEvent,
        value_name: str,
        *,
        item_return_count: int | None = None,
    ):
        data = None

        for entry in event.interaction.components:
            if entry.component.custom_id == value_name:
                data = (
                    entry.component.value
                    if isinstance(entry.component, TextInputInteractionComponent)
                    else entry.component.values
                    if isinstance(
                        entry.component,
                        (
                            TextSelectMenuInteractionComponent,
                            FileUploadInteractionComponent,
                        ),
                    )
                    else None
                )

        if isinstance(data, list) and item_return_count is not None:
            data = [data.pop(0) for _ in range(item_return_count)]

        return data

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
        if not ENABLE_CUSTOM_NAME_AND_AVATARS and id_data in (
            "custom_name",
            "custom_avatar",
        ):
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.only_custom_instances",
                    user_config.primary_language,
                )
            )
            return

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

        if id_data == "custom_avatar":
            item = None
            item_id = cls.extract_value(event, "avatar")
            if item_id:
                assert event.interaction.resolved is not None
                assert isinstance(item_id, list)
                assert len(item_id) == 1
                item_id: int = item_id[0]
                item: hikari.messages.Attachment | None = (
                    event.interaction.resolved.attachments.get(
                        cast("hikari.Snowflake", item_id)
                    )
                )

            await ctx.client.rest.edit_my_member(guild_config.guild_id, avatar=item)
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.changed_avatar",
                    user_config.primary_language,
                ),
                ephemeral=True,
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

        elif id_data == "premium_modal_custom_avatar":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_avatar.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:custom_avatar",
                components=await cls.build_avatar_modal(localisations, user_config),
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
    async def build_avatar_modal(
        cls, localisations: Localisation, user_config: UserConfigs
    ):
        return [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_avatar.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_avatar.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.FileUploadComponentBuilder(
                    custom_id="avatar",
                    min_values=0,
                    max_values=1,
                    is_required=False,
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
