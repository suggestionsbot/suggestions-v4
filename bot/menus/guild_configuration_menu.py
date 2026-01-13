from datetime import timedelta
from typing import Sequence

import hikari
import lightbulb
import orjson
from hikari.api import special_endpoints

from bot.localisation import Localisation
from shared.tables import GuildConfigs
from web import constants as t_constants


class GuildConfigurationMenus:
    @classmethod
    async def build_base_components(
        cls,
        *,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        components: list[special_endpoints.ComponentBuilder] = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.guild_configuration.base_menu.overall_description", ctx
                )
            )
        ]
        # Add suggestions container
        current_channel_placeholder: str | None = None
        if guild_config.suggestions_channel_id:
            cache_key = f"guilds:{ctx.guild_id}:channel_names:{guild_config.suggestions_channel_id}"
            current_channel_placeholder: bytes | None = (
                await t_constants.REDIS_CLIENT.get(cache_key)
            )
            if current_channel_placeholder is not None:
                try:
                    current_channel_placeholder: str = current_channel_placeholder.decode(
                        "utf-8"
                    )
                except UnicodeDecodeError:
                    pass

            elif current_channel_placeholder is None:
                try:
                    channel = await ctx.client.rest.fetch_channel(
                        guild_config.suggestions_channel_id
                    )
                    current_channel_placeholder: str = f"#{channel.name}"
                    await t_constants.REDIS_CLIENT.set(
                        cache_key,
                        current_channel_placeholder.encode("utf-8"),
                        ex=timedelta(minutes=15),
                    )
                except (hikari.errors.HikariError, UnicodeEncodeError):
                    pass

        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestion_name", ctx
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id="gcm:suggestions_channel",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=current_channel_placeholder,
                            ),  # type: ignore
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.threads_for_suggestions",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:threads_for_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=guild_config.threads_for_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=not guild_config.threads_for_suggestions,
                                    ),
                                ],
                            ),
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.auto_archive_threads",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:auto_archive_threads",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=guild_config.auto_archive_threads,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=not guild_config.auto_archive_threads,
                                    ),
                                ],
                            ),
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.can_have_anonymous_suggestions",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:can_have_anonymous_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=guild_config.can_have_anonymous_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=not guild_config.can_have_anonymous_suggestions,
                                    ),
                                ],
                            ),
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.can_have_images_in_suggestions",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:can_have_images_in_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=guild_config.can_have_images_in_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=not guild_config.can_have_images_in_suggestions,
                                    ),
                                ],
                            ),
                        ]
                    ),
                ]
            )
        )

        # Add log container
        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.log_channel.description",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:log_channel",
                                options=[
                                    # If this, set keep logs
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.log_channel.same_channel",
                                            ctx,
                                        ),
                                        value="same_channel",
                                        is_default=guild_config.keep_logs,
                                    ),
                                    # If this, make another menu for where to go
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.log_channel.dedicated_channel",
                                            ctx,
                                        ),
                                        value="dedicated_channel",
                                        is_default=(
                                            True
                                            if guild_config.keep_logs is False
                                            and guild_config.log_channel_id is not None
                                            else False
                                        ),
                                    ),
                                ],
                            ),
                        ]
                    ),
                ]
            )
        )

        # Add queue container
        no_queue_is_default = not guild_config.uses_suggestions_queue
        virtual_is_default = False
        channel_is_default = False
        if guild_config.uses_suggestions_queue:
            if guild_config.virtual_suggestions_queue:
                virtual_is_default = True
            else:
                channel_is_default = True
        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestion_queue.description",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:suggestions_queue",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.none",
                                            ctx,
                                        ),
                                        value="none",
                                        is_default=no_queue_is_default,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.virtual",
                                            ctx,
                                        ),
                                        value="virtual",
                                        is_default=virtual_is_default,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.channel",
                                            ctx,
                                        ),
                                        value="channel",
                                        is_default=channel_is_default,
                                    ),
                                ],
                            ),
                        ]
                    ),
                ]
            )
        )

        # Docs for extra info
        components.append(
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/configuration",
                        label="View the documentation here",
                    ),
                ]
            )
        )

        return components
