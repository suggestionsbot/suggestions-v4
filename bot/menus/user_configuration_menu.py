import logging
from datetime import timedelta
from collections.abc import Sequence
from typing import cast

import commons
import hikari
import lightbulb
from hikari.api import special_endpoints

from bot import utils, constants
from bot.exceptions import SuggestionException
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs
from shared.utils import configs
from shared.utils.locales import language_as_word

log = logging.getLogger(__name__)


class UserConfigurationMenus:
    @classmethod
    async def handle_interaction(  # noqa: PLR0912, PLR0911, PLR0915, C901
        cls,
        id_data: str,
        *,
        ctx: lightbulb.components.MenuContext,
        event: hikari.ComponentInteractionCreateEvent,
        link_id: str,
    ) -> None:
        await ctx.defer(ephemeral=True)
        user_config = await configs.ensure_user_config(cast("int", ctx.user.id))
        event_values: Sequence[str] = event.interaction.values
        log.debug(
            "Processing UCM component %s",
            id_data,
            extra={
                "setting.new_value": (
                    event_values[0] if len(event_values) == 1 else event_values
                ),
            },
        )
        if id_data == "ping_on_thread_creation":
            # These are all bool answers so is fine to do as is
            result = commons.value_to_bool(event_values[0])
            user_config.ping_on_thread_creation = result
            await user_config.save()
            key = "enabled" if getattr(user_config, id_data) else "disabled"
            await ctx.respond(
                constants.LOCALISATIONS.get_localized_string(
                    f"menus.user_configuration.responses.{id_data}.{key}",
                    user_config.primary_language,
                ),
            )
            return

        if id_data == "generic_dm_messages_disabled":
            # Flipped for legacy purposes to maintain translations
            # These are all bool answers so is fine to do as is
            result = not commons.value_to_bool(event_values[0])
            user_config.generic_dm_messages_disabled = result
            await user_config.save()
            key = "enabled" if not getattr(user_config, id_data) else "disabled"
            await ctx.respond(
                constants.LOCALISATIONS.get_localized_string(
                    f"menus.user_configuration.responses.{id_data}.{key}",
                    user_config.primary_language,
                ),
            )
            return

        if id_data == "primary_language":
            user_config.primary_language_raw = event_values[0]
            await user_config.save()
            await ctx.respond(
                constants.LOCALISATIONS.get_localized_string(
                    "menus.guild_configuration.responses.primary_language",
                    user_config.primary_language,
                    extras={
                        "LANGUAGE": language_as_word(user_config.primary_language_raw)
                    },
                ),
            )
            return

        msg = f"Unknown UCM interaction -> {id_data!r}"
        raise SuggestionException(msg)

    @classmethod
    async def build_base_components_page_1(
        cls,
        *,
        user_config: UserConfigs,
        localisations: Localisation,
        link_id: str | None = None,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        if link_id is None:
            link_id = await utils.otel.generate_trace_link_state()

        components: list[special_endpoints.ComponentBuilder] = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.user_configuration.base_menu.overall_description",
                    user_config.primary_language,
                ),
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.user_configuration.base_menu.generic_dm_messages_disabled",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"ucm:{link_id}:generic_dm_messages_disabled",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.user_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=not user_config.generic_dm_messages_disabled,  # noqa: E501
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.user_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=user_config.generic_dm_messages_disabled,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.user_configuration.base_menu.ping_on_thread_creation",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"ucm:{link_id}:ping_on_thread_creation",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.user_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=user_config.ping_on_thread_creation,  # noqa: E501
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.user_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not user_config.ping_on_thread_creation,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.user_configuration.base_menu.primary_language",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"ucm:{link_id}:primary_language",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=k,
                                        value=v,
                                        is_default=user_config.primary_language_raw == v,
                                    )
                                    for k, v in {
                                        "Danish": "da",
                                        "English, UK": "en-GB",
                                        "English, US": "en-US",
                                        "French": "fr",
                                        "German": "de",
                                        "Portuguese, Brazilian": "pt-BR",
                                    }.items()
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/user-configuration",
                        label="View the documentation here",
                    ),
                ],
            ),
        ]

        return components
