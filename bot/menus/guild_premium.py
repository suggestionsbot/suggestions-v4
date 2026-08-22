import bot.constants
from web.constants import REDIS_CLIENT
import logging
from collections.abc import Sequence
from typing import cast, Literal

import hikari
import lightbulb
from hikari.api import special_endpoints
from hikari.interactions.interaction_components import (
    TextInputInteractionComponent,
    TextSelectMenuInteractionComponent,
    FileUploadInteractionComponent,
)

from bot import utils
from bot.constants import ENABLE_CUSTOM_NAME_AND_AVATARS, IS_CUSTOM_BOT
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs
from shared.tables.premium_guild_config import CooldownPeriod

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

        elif id_data == "custom_avatar":
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

        elif id_data in ("custom_suggestion_prefix", "custom_queued_suggestion_prefix"):
            prefix: str | None = cast("str | None", cls.extract_value(event, "prefix"))
            if (
                prefix is not None
                and not IS_CUSTOM_BOT
                and ("@everyone" in prefix or "@here" in prefix)
            ):
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.premium_menu.responses.no_everyone",
                        user_config.primary_language,
                    )
                )
                return

            roles: list[str] = cast("list[str]", cls.extract_value(event, "roles"))
            roles_text: str = " ".join(f"<@&{role_id}>" for role_id in roles)
            if roles:
                if prefix:
                    prefix += "\n\n"
                    prefix += roles_text
                else:
                    prefix = roles_text

            prefix = prefix or None
            if id_data == "custom_queued_suggestion_prefix":
                guild_config.premium.queued_suggestions_prefix = prefix
            else:
                guild_config.premium.suggestions_prefix = prefix
            await guild_config.premium.save()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.changed_suggestions_prefix",
                    user_config.primary_language,
                )
            )

        elif id_data == "custom_cooldowns":
            amount: str = cast("str", cls.extract_value(event, "amount"))
            if not amount.isdigit():
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.premium_menu.responses.must_be_numeric",
                        user_config.primary_language,
                    )
                )
                return

            period: list[str] = cast("list[str] ", cls.extract_value(event, "period"))
            period_enum = CooldownPeriod(period[0])

            guild_config.premium.cooldown_period = period_enum
            guild_config.premium.cooldown_amount = int(amount)
            await guild_config.premium.save()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.set_custom_cooldown",
                    user_config.primary_language,
                    extras={"AMOUNT": amount, "PERIOD": period_enum.value},
                )
            )

        elif id_data == "suggest_button_message":
            message: str | None = cast("str|None", cls.extract_value(event, "message"))
            button_message: str | None = cast(
                "str|None", cls.extract_value(event, "button")
            )
            guild_config.premium.suggestion_button_message_prefix = message or None
            guild_config.premium.suggestion_button_message = button_message or None
            await guild_config.premium.save()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.configured_physical_button_messages",
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

        elif id_data == "premium_modal_custom_avatar":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_avatar.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:custom_avatar",
                components=await cls.build_avatar_modal(localisations, user_config),
            )

        elif id_data == "premium_modal_suggestions_prefix":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_suggestion_prefix.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:custom_suggestion_prefix",
                components=await cls.build_prefix_modal(
                    localisations, user_config, "suggestion"
                ),
            )

        elif id_data == "premium_modal_queued_suggestion_prefix":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_queued_suggestion_prefix.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:custom_queued_suggestion_prefix",
                components=await cls.build_prefix_modal(
                    localisations, user_config, "queued_suggestion"
                ),
            )
        elif id_data == "premium_modal_cooldowns":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_cooldown.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:custom_cooldowns",
                components=await cls.build_cooldown_modal(
                    localisations,
                    user_config,
                ),
            )
        elif id_data == "premium_modal_suggest_button":
            await ctx.respond_with_modal(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.suggestion_button_message.modal_title",
                    user_config.primary_language,
                ),
                f"guild_premium_modal:{link_id}:suggest_button_message",
                components=await cls.build_suggest_button_modal(
                    localisations,
                    user_config,
                ),
            )

        await ctx.defer(ephemeral=True)

        if id_data == "premium_remove_custom_cooldowns":
            guild_config.premium.cooldown_amount = None
            await guild_config.premium.save()

            # Delete this so it also resets peoples cooldowns
            await REDIS_CLIENT.delete(f"premium:custom_cooldown:{guild_config.guild_id}")
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.responses.reset_custom_cooldown",
                    user_config.primary_language,
                )
            )

    @classmethod
    async def build_prefix_modal(
        cls,
        localisations: Localisation,
        user_config: UserConfigs,
        prefix: Literal["suggestion", "queued_suggestion"],
    ):
        key = f"custom_{prefix}_prefix"
        return [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    f"menus.guild_configuration.premium_menu.{key}.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    f"menus.guild_configuration.premium_menu.{key}.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="prefix",
                    style=hikari.TextInputStyle.SHORT,
                    required=False,
                    min_length=1,
                    max_length=150,
                ),
            ),
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_prefix_roles.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_prefix_roles.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.SelectMenuBuilder(
                    type=hikari.ComponentType.ROLE_SELECT_MENU,
                    custom_id="roles",
                    min_values=1,
                    max_values=15,
                    is_required=False,
                ),
            ),
        ]

    @classmethod
    async def build_cooldown_modal(
        cls, localisations: Localisation, user_config: UserConfigs
    ):
        return [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_cooldown.amount.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_cooldown.amount.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="amount",
                    style=hikari.TextInputStyle.SHORT,
                    required=True,
                    min_length=1,
                    max_length=10,
                ),
            ),
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_cooldown.period.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.custom_cooldown.period.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextSelectMenuBuilder(
                    custom_id="period",
                    min_values=1,
                    max_values=1,
                    is_required=True,
                    options=[
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.guild_configuration.premium_menu.custom_cooldown.amount.options.hour",
                                user_config.primary_language,
                            ),
                            value="Hour",
                            is_default=True,
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.guild_configuration.premium_menu.custom_cooldown.amount.options.day",
                                user_config.primary_language,
                            ),
                            value="Day",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.guild_configuration.premium_menu.custom_cooldown.amount.options.week",
                                user_config.primary_language,
                            ),
                            value="Week",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.guild_configuration.premium_menu.custom_cooldown.amount.options.fortnight",
                                user_config.primary_language,
                            ),
                            value="Fortnight",
                        ),
                        hikari.impl.SelectOptionBuilder(
                            label=localisations.get_localized_string(
                                "menus.guild_configuration.premium_menu.custom_cooldown.amount.options.month",
                                user_config.primary_language,
                            ),
                            value="Month",
                        ),
                    ],
                ),
            ),
        ]

    @classmethod
    async def build_suggest_button_modal(
        cls, localisations: Localisation, user_config: UserConfigs
    ):
        return [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.suggestion_button_message.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.suggestion_button_message.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="message",
                    style=hikari.TextInputStyle.PARAGRAPH,
                    required=False,
                    min_length=1,
                    max_length=bot.constants.MAX_CONTENT_LENGTH,
                ),
            ),
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.suggestion_button.title",
                    user_config.primary_language,
                ).capitalize(),
                description=localisations.get_localized_string(
                    "menus.guild_configuration.premium_menu.suggestion_button.description",
                    user_config.primary_language,
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="button",
                    style=hikari.TextInputStyle.SHORT,
                    required=False,
                    min_length=1,
                    max_length=100,
                ),
            ),
        ]

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
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.custom_details.name",
                                    user_config.primary_language,
                                ),
                                custom_id=f"gcm:{link_id}:premium_modal_custom_name",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.custom_details.avatar",
                                    user_config.primary_language,
                                ),
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
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.suggestion_prefix.suggestion",
                                    user_config.primary_language,
                                ),
                                custom_id=f"gcm:{link_id}:premium_modal_suggestions_prefix",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.suggestion_prefix.queued_suggestion",
                                    user_config.primary_language,
                                ),
                                custom_id=f"gcm:{link_id}:premium_modal_queued_suggestion_prefix",
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.premium_menu.custom_cooldowns",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.custom_cooldowns.add",
                                    user_config.primary_language,
                                ),
                                custom_id=f"gcm:{link_id}:premium_modal_cooldowns",
                            ),
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.SECONDARY,
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.premium_menu.custom_cooldowns.remove",
                                    user_config.primary_language,
                                ),
                                custom_id=f"gcm:{link_id}:premium_remove_custom_cooldowns",
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
                        url="https://docs.suggestions.gg/docs/premium",
                        label=localisations.get_localized_string(
                            "menus.guild_configuration.view_premium_docs",
                            user_config.primary_language,
                        ),
                    ),
                ],
            ),
        ]

        # Pagination

        # Docs for extra info

        return components
