from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

import hikari

from bot.constants import LOCALISATIONS, EMBED_COLOR
from bot.utils import fetch_user_avatar
from shared.tables import (
    UserConfigs,
    Suggestions,
    QueuedSuggestions,
    QueuedSuggestionStateEnum,
)

if TYPE_CHECKING:
    from hikari.api import ContainerComponentBuilder, MessageActionRowBuilder
logger = logging.getLogger(__name__)


async def build_new_suggestion_notification(
    *,
    user_config: UserConfigs,
    suggestion: Suggestions,
) -> list[hikari.impl.ContainerComponentBuilder]:
    return [
        hikari.impl.ContainerComponentBuilder(
            accent_color=EMBED_COLOR,
            components=[
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "saq.notify_users_of_new_suggestion.responses.suggestion_created",
                        user_config.primary_language,
                        extras={
                            "AUTHOR": suggestion.author_display_name,
                            "CHANNEL": f"<#{suggestion.channel_id}>",
                            "SUGGESTION_LINK": suggestion.message_jump_link,
                        },
                    ),
                ),
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                ),
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "commands.note.add.responses.dm_change_footer",
                        user_config.primary_language,
                        extras={
                            "GUILD_ID": suggestion.guild_id,
                            "SID": suggestion.footer_sid,
                        },
                    ),
                ),
            ],
        ),
    ]


async def build_user_resolution_notification(
    *,
    user_config: UserConfigs,
    suggestion: Suggestions,
) -> list[hikari.impl.ContainerComponentBuilder]:
    return [
        hikari.impl.ContainerComponentBuilder(
            accent_color=suggestion.color,
            components=[
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "saq.suggestion_resolved_notifications.responses.suggestion_resolved.description",
                        user_config.primary_language,
                        extras={
                            "AUTHOR": suggestion.author_display_name,
                            "STATE": suggestion.state.value,
                            "JUMP_TO": suggestion.message_jump_link,
                            "RESOLVED_BY": suggestion.resolved_by_display_text,
                            "SID": f"**{suggestion.sID}**",
                        },
                    ),
                ),
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                ),
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "saq.suggestion_resolved_notifications.responses.suggestion_resolved.footer",
                        user_config.primary_language,
                        extras={
                            "GUILD_ID": suggestion.guild_id,
                            "SID": suggestion.footer_sid,
                        },
                    ),
                ),
            ],
        ),
    ]


async def build_queued_user_resolution_notification(
    *,
    user_config: UserConfigs,
    suggestion: QueuedSuggestions,
    rest: hikari.api.RESTClient,
) -> list[ContainerComponentBuilder | MessageActionRowBuilder]:
    extra = None
    if suggestion.state == QueuedSuggestionStateEnum.APPROVED:
        related_suggestion: Suggestions = suggestion.related_suggestion
        related_suggestion.guild_configuration = await related_suggestion.get_related(
            Suggestions.guild_configuration,
        )
        jump_to = related_suggestion.message_jump_link
        initial_cv = hikari.impl.TextDisplayComponentBuilder(
            content=LOCALISATIONS.get_localized_string(
                "saq.queued_suggestion_resolved_notifications.responses.approved.description",
                user_config.primary_language,
                extras={
                    "AUTHOR": suggestion.author_display_name,
                    "JUMP_TO": jump_to,
                    "RESOLVED_BY": suggestion.resolved_by_display_text,
                    "SID": f"**{suggestion.sID}**",
                },
            ),
        )
    else:
        initial_cv = hikari.impl.TextDisplayComponentBuilder(
            content=LOCALISATIONS.get_localized_string(
                "saq.queued_suggestion_resolved_notifications.responses.rejected.description",
                user_config.primary_language,
                extras={
                    "AUTHOR": suggestion.author_display_name,
                    "RESOLVED_BY": suggestion.resolved_by_display_text,
                    "SID": f"**{suggestion.sID}**",
                },
            ),
        )
        extra = await suggestion.as_components(
            rest=rest,
            locale=user_config.primary_language,
            localisations=LOCALISATIONS,
            include_buttons=False,
        )

    data: list[ContainerComponentBuilder | MessageActionRowBuilder] = [
        hikari.impl.ContainerComponentBuilder(
            accent_color=suggestion.color,
            components=[
                initial_cv,
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                ),
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string(
                        "saq.queued_suggestion_resolved_notifications.responses.suggestion_resolved.footer",
                        user_config.primary_language,
                        extras={
                            "GUILD_ID": suggestion.guild_id,
                            "SID": suggestion.footer_sid,
                        },
                    ),
                ),
            ],
        ),
    ]
    if extra is not None:
        data.extend(extra)

    return data


class SegmentData(Protocol):
    is_anonymous: bool
    author_display_name: str
    sID: str


async def insert_user_segment(
    *,
    user_id: int,
    data: SegmentData,
    rest: hikari.api.RESTClient,
    components: list,
    locale: hikari.Locale | str,
    locale_key: str,
) -> None:
    """Safely insert user segments that handle 415 status codes."""
    user_avatar = await fetch_user_avatar(user_id=user_id, rest=rest)
    if not data.is_anonymous and user_avatar is None:
        logger.debug(
            "Skipping avatar for %s %s as the avatar is not available",
            data.__class__.__name__,
            data.sID,
            extra={
                "interaction.user.id": user_id,
            },
        )

    if data.is_anonymous or user_avatar is None:
        components.append(
            hikari.impl.TextDisplayComponentBuilder(
                content=LOCALISATIONS.get_localized_string(
                    locale_key,
                    locale,
                    extras={"AUTHOR_DISPLAY": data.author_display_name},
                )
            )
        )

    else:
        assert user_avatar is not None
        components.append(
            hikari.impl.SectionComponentBuilder(
                components=[
                    hikari.impl.TextDisplayComponentBuilder(
                        content=LOCALISATIONS.get_localized_string(
                            locale_key,
                            locale,
                            extras={"AUTHOR_DISPLAY": data.author_display_name},
                        )
                    ),
                ],
                accessory=hikari.impl.ThumbnailComponentBuilder(
                    media=user_avatar,
                ),
            )
        )
