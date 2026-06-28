import logging
from datetime import timedelta
from collections.abc import Sequence
from typing import cast

import commons
import hikari
import lightbulb
from hikari.api import special_endpoints, ComponentBuilder

from bot import utils
from bot.exceptions import SuggestionException
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs
from shared.utils import configs, get_cached_interaction_id
from shared.utils.locales import language_as_word
from web import constants as t_constants
import contextlib

log = logging.getLogger(__name__)


class GuildConfigurationMenus:
    @classmethod
    async def handle_interaction(  # noqa: PLR0912, PLR0911, PLR0915, C901
        cls,
        id_data: str,
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        event: hikari.ComponentInteractionCreateEvent,
        link_id: str,
    ) -> None:
        await ctx.defer(ephemeral=True)
        user_config = await configs.ensure_user_config(
            cast("int", ctx.user.id), locale=ctx.interaction.locale
        )
        guild_config = await configs.ensure_guild_config(cast("int", ctx.guild_id))
        event_values: Sequence[str] = event.interaction.values
        log.debug(
            "Processing GCM component %s",
            id_data,
            extra={
                "setting.new_value": (
                    event_values[0] if len(event_values) == 1 else event_values
                ),
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
                await ctx.respond(
                    localisations.get_localized_string(
                        f"menus.guild_configuration.responses.{id_data}.empty",
                        user_config.primary_language,
                    ),
                    ephemeral=True,
                )
                return

            setattr(guild_config, id_data, int(event_values[0]))
            if id_data == "log_channel_id":
                guild_config.keep_logs = False

            elif id_data in (  # noqa: FURB171
                "queued_suggestion_channel_id",
                # Can set logs channel without breaking virtual queue
                # "queued_suggestion_log_channel_id",
            ):
                guild_config.uses_suggestion_queue = True
                guild_config.virtual_suggestions_queue = False

            await guild_config.save()
            await ctx.respond(
                localisations.get_localized_string(
                    f"menus.guild_configuration.responses.{id_data}.set",
                    user_config.primary_language,
                    extras={"CHANNEL": f"<#{getattr(guild_config, id_data)}>"},
                ),
                ephemeral=True,
            )
            return

        if id_data in (
            "threads_for_suggestions",
            "auto_archive_threads",
            "can_have_anonymous_suggestions",
            "can_have_images_in_suggestions",
            "ping_on_thread_creation",
            "allow_anonymous_moderators",
        ):
            # These are all bool answers so is fine to do as is
            result = commons.value_to_bool(event_values[0])
            setattr(guild_config, id_data, result)
            await guild_config.save()
            key = "enabled" if getattr(guild_config, id_data) else "disabled"
            await ctx.respond(
                localisations.get_localized_string(
                    f"menus.guild_configuration.responses.{id_data}.{key}",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return

        if id_data == "generic_dm_messages_disabled":
            # Flipped for legacy purposes to maintain translations
            # These are all bool answers so is fine to do as is
            result = not commons.value_to_bool(event_values[0])
            setattr(guild_config, id_data, result)
            await guild_config.save()
            key = "enabled" if not getattr(guild_config, id_data) else "disabled"
            await ctx.respond(
                localisations.get_localized_string(
                    f"menus.guild_configuration.responses.{id_data}.{key}",
                    user_config.primary_language,
                ),
            )
            return

        if id_data == "primary_language":
            guild_config.primary_language_raw = event_values[0]
            await guild_config.save()
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.responses.primary_language",
                    user_config.primary_language,
                    extras={
                        "LANGUAGE": language_as_word(guild_config.primary_language_raw)
                    },
                ),
            )
            return

        if id_data == "log_channel":
            if event_values[0] == "same_channel":
                guild_config.keep_logs = True
                await guild_config.save()
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.keep_logs.set",
                        user_config.primary_language,
                    ),
                )
                return

            # We need to pick a channel
            await ctx.respond(
                components=await cls.build_log_channel_components(
                    ctx=ctx,
                    localisations=localisations,
                    guild_config=guild_config,
                    link_id=link_id,
                    user_config=user_config,
                ),
            )
            return

        if id_data == "send_suggestions_button":
            channel = int(event_values[0])
            await ctx.client.rest.create_message(
                channel,
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.responses.sent_suggestions_button.description",
                            guild_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.InteractiveButtonBuilder(
                                style=hikari.ButtonStyle.PRIMARY,
                                label=localisations.get_localized_string(
                                    "menus.guild_configuration.responses.sent_suggestions_button.button",
                                    guild_config.primary_language,
                                ),
                                custom_id="v4_suggest_button",
                            ),
                        ],
                    ),
                ],
            )
            await ctx.respond(
                localisations.get_localized_string(
                    "menus.guild_configuration.responses.sent_suggestions_button",
                    guild_config.primary_language,
                ),
            )
            return

        if id_data == "view_page_2":
            original_id = await get_cached_interaction_id(link_id)
            if original_id is None:
                await ctx.respond(
                    components=await cls.build_base_components_page_2(
                        ctx=ctx,
                        localisations=localisations,
                        guild_config=guild_config,
                        link_id=link_id,
                        user_config=user_config,
                    ),
                )
            else:
                await ctx.edit_response(
                    original_id,
                    components=await cls.build_base_components_page_2(
                        ctx=ctx,
                        localisations=localisations,
                        guild_config=guild_config,
                        link_id=link_id,
                        user_config=user_config,
                    ),
                )
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.changed_page_inline",
                        user_config.primary_language,
                    ),
                    ephemeral=True,
                )
            return

        if id_data == "view_page_1":
            original_id = await get_cached_interaction_id(link_id)
            if original_id is None:
                await ctx.respond(
                    components=await cls.build_base_components_page_1(
                        ctx=ctx,
                        localisations=localisations,
                        guild_config=guild_config,
                        link_id=link_id,
                        user_config=user_config,
                    ),
                )
            else:
                await ctx.edit_response(
                    original_id,
                    components=await cls.build_base_components_page_1(
                        ctx=ctx,
                        localisations=localisations,
                        guild_config=guild_config,
                        link_id=link_id,
                        user_config=user_config,
                    ),
                )
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.changed_page_inline",
                        user_config.primary_language,
                    ),
                    ephemeral=True,
                )
            return

        if id_data == "suggestions_queue":
            value = event_values[0]
            if value == "none":
                guild_config.uses_suggestion_queue = False
                await guild_config.save()
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.suggestion_queue.none",
                        user_config.primary_language,
                    ),
                )
                return

            if value == "virtual":
                guild_config.uses_suggestion_queue = True
                guild_config.virtual_suggestions_queue = True
                guild_config.queued_suggestion_channel_id = None
                # Leave log channel alone so they keep getting logged
                await guild_config.save()
                await ctx.respond(
                    localisations.get_localized_string(
                        "menus.guild_configuration.responses.suggestion_queue.virtual",
                        user_config.primary_language,
                    ),
                )
                return

            if value == "channel":
                await ctx.respond(
                    components=await cls.build_queue_components(
                        ctx=ctx,
                        localisations=localisations,
                        guild_config=guild_config,
                        link_id=link_id,
                        user_config=user_config,
                    ),
                )
                return

        msg = f"Unknown gcm interaction -> {id_data!r}"
        raise SuggestionException(msg)

    @classmethod
    async def get_channel_name(
        cls,
        field: str,
        *,
        ctx: lightbulb.components.MenuContext | lightbulb.Context,
        guild_config: GuildConfigs,
    ) -> str | hikari.UndefinedType:
        current_channel_placeholder: str | None = None
        if getattr(guild_config, field):
            cache_key = (
                f"guilds:{ctx.guild_id}:channel_names:{getattr(guild_config, field)}"
            )
            current_channel_placeholder = await t_constants.REDIS_CLIENT.get(
                cache_key
            )  # ty:ignore[invalid-assignment]
            if current_channel_placeholder is not None and isinstance(
                current_channel_placeholder, bytes
            ):
                with contextlib.suppress(UnicodeDecodeError):
                    current_channel_placeholder: str = current_channel_placeholder.decode(
                        "utf-8",
                    )

            elif current_channel_placeholder is None:
                try:
                    channel = await ctx.client.rest.fetch_channel(
                        getattr(guild_config, field),
                    )
                    current_channel_placeholder: str = f"#{channel.name}"
                    await t_constants.REDIS_CLIENT.set(
                        cache_key,
                        current_channel_placeholder.encode("utf-8"),
                        ex=timedelta(minutes=15),
                    )
                except (hikari.errors.HikariError, UnicodeEncodeError):
                    pass

        return (
            current_channel_placeholder
            if current_channel_placeholder is not None
            and isinstance(current_channel_placeholder, str)
            else hikari.UNDEFINED
        )

    @classmethod
    async def build_queue_components(
        cls,
        *,
        ctx: lightbulb.components.MenuContext | lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        link_id: str | None = None,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        if link_id is None:
            link_id = await utils.otel.generate_trace_link_state()

        return [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.guild_configuration.queue_menu.overall_description",
                    user_config.primary_language,
                ),
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.queue_menu.queued_suggestion_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:queued_suggestion_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "queued_suggestion_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.queue_menu.queued_suggestion_log_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:queued_suggestion_log_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "queued_suggestion_log_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
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
                        url="https://docs.suggestions.gg/docs/queue",
                        label="View queue documentation here for more information",
                    ),
                ],
            ),
        ]

        # Docs for extra info

    @classmethod
    async def build_log_channel_components(
        cls,
        *,
        ctx: lightbulb.components.MenuContext | lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        link_id: str | None = None,
    ) -> Sequence[special_endpoints.ComponentBuilder]:
        if link_id is None:
            link_id = await utils.otel.generate_trace_link_state()

        return [
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.log_menu.log_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:log_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "log_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
        ]

    @classmethod
    async def build_setup_components(
        cls,
        *,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        link_id: str | None = None,
    ) -> list[ComponentBuilder]:
        if link_id is None:
            link_id = await utils.otel.generate_trace_link_state()

        no_queue_is_default = not guild_config.uses_suggestion_queue
        virtual_is_default = False
        channel_is_default = False
        if guild_config.uses_suggestion_queue:
            if guild_config.virtual_suggestions_queue:
                virtual_is_default = True
            else:
                channel_is_default = True

        components: list[special_endpoints.ComponentBuilder] = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.setup.base_menu.overall_description",
                    user_config.primary_language,
                ),
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestions_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:suggestions_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "suggestions_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.threads_for_suggestions",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:threads_for_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.threads_for_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.threads_for_suggestions,  # noqa: E501
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.log_menu.log_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:log_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "log_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "menus.setup.base_menu.optional_description",
                    user_config.primary_language,
                ),
            ),
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestion_queue.description",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:suggestions_queue",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.none",
                                            user_config.primary_language,
                                        ),
                                        value="none",
                                        is_default=no_queue_is_default,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.virtual",
                                            user_config.primary_language,
                                        ),
                                        value="virtual",
                                        is_default=virtual_is_default,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.channel",
                                            user_config.primary_language,
                                        ),
                                        value="channel",
                                        is_default=channel_is_default,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestions_via_button",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:send_suggestions_button",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.update_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:update_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "update_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=0,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/guild-configuration",
                        label="View more documentation here",
                    ),
                ],
            ),
        ]
        return components

    @classmethod
    async def build_base_components_page_1(
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
                            "menus.guild_configuration.base_menu.suggestions_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:suggestions_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "suggestions_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.threads_for_suggestions",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:threads_for_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.threads_for_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.threads_for_suggestions,  # noqa: E501
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.auto_archive_threads",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:auto_archive_threads",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.auto_archive_threads,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.auto_archive_threads,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.ping_on_thread_creation",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:ping_on_thread_creation",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.ping_on_thread_creation,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.ping_on_thread_creation,  # noqa: E501
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.can_have_anonymous_suggestions",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:can_have_anonymous_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.can_have_anonymous_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.can_have_anonymous_suggestions,  # noqa: E501
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.can_have_images_in_suggestions",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:can_have_images_in_suggestions",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.can_have_images_in_suggestions,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.can_have_images_in_suggestions,  # noqa: E501
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestions_via_button",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:send_suggestions_button",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                min_values=1,
                                max_values=1,
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
                            "menus.guild_configuration.responses.pagination.view_next",
                            user_config.primary_language,
                        ),
                        custom_id=f"gcm:{link_id}:view_page_2",
                    ),
                ],
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/guild-configuration",
                        label="View the documentation here",
                    ),
                ],
            ),
        ]
        # Add suggestions container

        # Add log container

        # Pagination

        # Docs for extra info

        return components

    @classmethod
    async def build_base_components_page_2(
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
        ]

        # Add queue container
        no_queue_is_default = not guild_config.uses_suggestion_queue
        virtual_is_default = False
        channel_is_default = False
        if guild_config.uses_suggestion_queue:
            if guild_config.virtual_suggestions_queue:
                virtual_is_default = True
            else:
                channel_is_default = True

        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.log_channel.description",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:log_channel",
                                options=[
                                    # If this, set keep logs
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.log_channel.same_channel",
                                            user_config.primary_language,
                                        ),
                                        value="same_channel",
                                        is_default=guild_config.keep_logs,
                                    ),
                                    # If this, make another menu for where to go
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.log_channel.dedicated_channel",
                                            user_config.primary_language,
                                        ),
                                        value="dedicated_channel",
                                        is_default=(
                                            bool(
                                                guild_config.keep_logs is False
                                                and guild_config.log_channel_id
                                                is not None,
                                            )
                                        ),
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.allow_anonymous_moderators",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:allow_anonymous_moderators",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=guild_config.allow_anonymous_moderators,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=not guild_config.allow_anonymous_moderators,  # noqa: E501
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
        )
        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.suggestion_queue.description",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:suggestions_queue",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.none",
                                            user_config.primary_language,
                                        ),
                                        value="none",
                                        is_default=no_queue_is_default,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.virtual",
                                            user_config.primary_language,
                                        ),
                                        value="virtual",
                                        is_default=virtual_is_default,
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.base_menu.suggestion_queue.channel",
                                            user_config.primary_language,
                                        ),
                                        value="channel",
                                        is_default=channel_is_default,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
        )

        # Add misc container
        components.append(
            hikari.impl.ContainerComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.generic_dm_messages_disabled",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:generic_dm_messages_disabled",
                                options=[
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.yes",
                                            user_config.primary_language,
                                        ),
                                        value="yes",
                                        is_default=not guild_config.generic_dm_messages_disabled,  # noqa: E501
                                    ),
                                    hikari.impl.SelectOptionBuilder(
                                        label=localisations.get_localized_string(
                                            "menus.guild_configuration.no",
                                            user_config.primary_language,
                                        ),
                                        value="no",
                                        is_default=guild_config.generic_dm_messages_disabled,
                                    ),
                                ],
                                min_values=1,
                                max_values=1,
                            ),
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.primary_language",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.TextSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:primary_language",
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
                        ],
                    ),
                    hikari.impl.TextDisplayComponentBuilder(
                        content=localisations.get_localized_string(
                            "menus.guild_configuration.base_menu.update_channel_id",
                            user_config.primary_language,
                        ),
                    ),
                    hikari.impl.MessageActionRowBuilder(
                        components=[
                            hikari.impl.ChannelSelectMenuBuilder(
                                custom_id=f"gcm:{link_id}:update_channel_id",
                                channel_types=[hikari.channels.ChannelType.GUILD_TEXT],
                                placeholder=await cls.get_channel_name(
                                    "update_channel_id",
                                    ctx=ctx,
                                    guild_config=guild_config,
                                ),
                                min_values=0,
                                max_values=1,
                            ),
                        ],
                    ),
                ],
            ),
        )
        # Pagination
        components.append(
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.PRIMARY,
                        label=localisations.get_localized_string(
                            "menus.guild_configuration.responses.pagination.view_previous",
                            user_config.primary_language,
                        ),
                        custom_id=f"gcm:{link_id}:view_page_1",
                    ),
                ],
            ),
        )

        # Docs for extra info
        components.append(
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.LinkButtonBuilder(
                        url="https://docs.suggestions.gg/docs/guild-configuration",
                        label="View the documentation here",
                    ),
                ],
            ),
        )

        return components
