import logging
from datetime import timedelta
from typing import Sequence

import commons
import hikari
import lightbulb
import orjson
from hikari.api import special_endpoints

from bot.exceptions import SuggestionException
from bot.localisation import Localisation
from shared.tables import GuildConfigs
from web import constants as t_constants

log = logging.getLogger(__name__)


class GuildConfigurationMenus:
    @classmethod
    async def handle_interaction(
        cls,
        id_data,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        event: hikari.ComponentInteractionCreateEvent,
    ):
        await ctx.defer(ephemeral=True)
        event_values: Sequence[str] = event.interaction.values
        log.debug(
            "Processing GCM component %s",
            id_data,
            extra={
                "setting.new_value": (
                    event_values[0] if len(event_values) == 1 else event_values
                )
            },
        )
        if id_data in (
            "suggestions_channel_id",
            "log_channel_id",
            "update_channel_id",
            "queued_suggestion_channel_id",
            "queued_suggestion_log_channel_id",
        ):
            if len(event_values) == 0:
                return await ctx.respond(
                    localisations.get_localized_string(
                        f"menus.guild_configuration.responses.{id_data}.empty",
                        ctx,
                    )
                )

            else:
                setattr(guild_config, id_data, int(event_values[0]))
                if id_data == "log_channel_id":
                    guild_config.keep_logs = False

                elif id_data in (
                    "queued_suggestion_channel_id",
                    "queued_suggestion_log_channel_id",
                ):
                    guild_config.uses_suggestions_queue = True
                    guild_config.virtual_suggestions_queue = False

                await guild_config.save()
                return await ctx.respond(
                    localisations.get_localized_string(
                        f"menus.guild_configuration.responses.{id_data}.set",
                        ctx,
                        extras={"CHANNEL": f"<#{getattr(guild_config, id_data)}>"},
                    )
                )

        elif id_data in (
            "threads_for_suggestions",
            "auto_archive_threads",
            "can_have_anonymous_suggestions",
            "can_have_images_in_suggestions",
            "ping_on_thread_creation",
            "anonymous_resolutions",
        ):
            # These are all bool answers so is fine to do as is
            result = commons.value_to_bool(event_values[0])
            setattr(guild_config, id_data, result)
            await guild_config.save()
            key = "enabled" if getattr(guild_config, id_data) else "disabled"
            return await ctx.respond(
                localisations.get_localized_string(
                    f"menus.guild_configuration.responses.{id_data}.{key}",
                    ctx,
                )
            )

        elif id_data in ("dm_messages_disabled",):
            # Flipped for legacy purposes to maintain translations
            # These are all bool answers so is fine to do as is
            result = not commons.value_to_bool(event_values[0])
            setattr(guild_config, id_data, result)
            await guild_config.save()
            key = "enabled" if not getattr(guild_config, id_data) else "disabled"
            return await ctx.respond(
                localisations.get_localized_string(
                    f"menus.guild_configuration.responses.{id_data}.{key}",
                    ctx,
                )
            )

        elif id_data == "primary_language":
            guild_config.primary_language_raw = event_values[0]
            await guild_config.save()
            return await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.responses.primary_language",
                    ctx,
                    extras={"LANGUAGE": guild_config.primary_language_as_word},
                )
            )

        elif id_data == "log_channel":
            if event_values[0] == "same_channel":
                guild_config.keep_logs = True
                await guild_config.save()
                return await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.keep_logs.set",
                        ctx,
                    )
                )

            else:
                # We need to pick a channel
                return await ctx.respond(
                    components=await cls.build_log_channel_components(
                        ctx=ctx, localisations=localisations, guild_config=guild_config
                    )
                )

        elif id_data == "view_page_2":
            return await ctx.respond(
                components=await cls.build_base_components_page_2(
                    ctx=ctx, localisations=localisations, guild_config=guild_config
                )
            )
        elif id_data == "view_page_1":
            return await ctx.respond(
                components=await cls.build_base_components_page_2(
                    ctx=ctx, localisations=localisations, guild_config=guild_config
                )
            )

        elif id_data == "suggestions_queue":
            value = event_values[0]
            if value == "none":
                guild_config.uses_suggestions_queue = False
                await guild_config.save()
                return await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.suggestion_queue.none", ctx
                    )
                )

            elif value == "virtual":
                guild_config.uses_suggestions_queue = True
                guild_config.virtual_suggestions_queue = True
                guild_config.queued_suggestion_channel_id = None
                guild_config.queued_suggestion_log_channel_id = None
                await guild_config.save()
                return await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.suggestion_queue.virtual",
                        ctx,
                    )
                )

            elif value == "channel":
                return await ctx.respond(
                    components=await cls.build_queue_components(
                        ctx=ctx, localisations=localisations, guild_config=guild_config
                    )
                )

        raise SuggestionException(f"Unknown gcm interaction -> {repr(id_data)}")

    @classmethod
    async def get_channel_name(
        cls,
        field: str,
        *,
        ctx: lightbulb.components.MenuContext | lightbulb.Context,
        guild_config: GuildConfigs,
    ) -> str:
        current_channel_placeholder: str | None = None
        if getattr(guild_config, field):
            cache_key = (
                f"guilds:{ctx.guild_id}:channel_names:{getattr(guild_config, field)}"
            )
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
                        getattr(guild_config, field)
                    )
                    current_channel_placeholder: str = f"#{channel.name}"
                    await t_constants.REDIS_CLIENT.set(
                        cache_key,
                        current_channel_placeholder.encode("utf-8"),
                        ex=timedelta(minutes=15),
                    )
                except (hikari.errors.HikariError, UnicodeEncodeError):
                    pass

        return current_channel_placeholder

    @classmethod
    async def build_queue_components(
        cls,
        *,
        ctx: lightbulb.components.MenuContext | lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        components = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.guild_configuration.queue_menu.overall_description", ctx
                )
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.queue_menu.queued_suggestion_channel_id",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id="gcm:queued_suggestion_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "queued_suggestion_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),  # type: ignore
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.queue_menu.queued_suggestion_log_channel_id",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id="gcm:queued_suggestion_log_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "queued_suggestion_log_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),  # type: ignore
                        ]
                    ),
                ]
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/queue",
                        label="View queue documentation here for more information",
                    ),
                ]
            ),
        ]

        # Docs for extra info
        return components

    @classmethod
    async def build_log_channel_components(
        cls,
        *,
        ctx: lightbulb.components.MenuContext | lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        return [
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.log_menu.log_channel_id", ctx
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id="gcm:log_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "log_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),  # type: ignore
                        ]
                    ),
                ]
            )
        ]

    @classmethod
    async def build_base_components_page_1(
        cls,
        *,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
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
        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestions_channel_id",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id="gcm:suggestions_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "suggestions_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
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
                                min_values=1,
                                max_values=1,
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
                                min_values=1,
                                max_values=1,
                            ),
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.ping_on_thread_creation",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:ping_on_thread_creation",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=guild_config.ping_on_thread_creation,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=not guild_config.ping_on_thread_creation,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
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
                                min_values=1,
                                max_values=1,
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
                                min_values=1,
                                max_values=1,
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
                                min_values=1,
                                max_values=1,
                            ),
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.anonymous_resolutions",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:anonymous_resolutions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=guild_config.anonymous_resolutions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=not guild_config.anonymous_resolutions,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ]
                    ),
                ]
            )
        )

        # Pagination
        components.append(
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.PRIMARY,
                        label=localisations.get_localized_string(
                            "menus.guild_configuration.responses.pagination.view_next",
                            ctx,
                        ),
                        custom_id="gcm:view_page_2",
                    ),
                ]
            ),
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

    @classmethod
    async def build_base_components_page_2(
        cls,
        *,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
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
                                min_values=1,
                                max_values=1,
                            ),
                        ]
                    ),
                ]
            )
        )

        # Add misc container
        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.dm_messages_disabled",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:dm_messages_disabled",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            ctx,
                                        ),
                                        value="yes",
                                        is_default=not guild_config.dm_messages_disabled,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            ctx,
                                        ),
                                        value="no",
                                        is_default=guild_config.dm_messages_disabled,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.primary_language",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id="gcm:primary_language",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=k,
                                        value=v,
                                        is_default=guild_config.primary_language_raw == v,
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
                        ]
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.update_channel_id",
                            ctx,
                        )
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id="gcm:update_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "update_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=0,
                                max_values=1,
                            ),  # type: ignore
                        ]
                    ),
                ]
            )
        )
        # Pagination
        components.append(
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.PRIMARY,
                        label=localisations.get_localized_string(
                            "menus.guild_configuration.responses.pagination.view_previous",
                            ctx,
                        ),
                        custom_id="gcm:view_page_1",
                    ),
                ]
            ),
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
