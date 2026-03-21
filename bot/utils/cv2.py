import hikari
from hikari.api import ContainerComponentBuilder, MessageActionRowBuilder

from bot.constants import LOCALISATIONS, EMBED_COLOR
from shared.tables import (
    UserConfigs,
    Suggestions,
    QueuedSuggestions,
    QueuedSuggestionStateEnum,
)


async def build_new_suggestion_notification(
    *, user_config: UserConfigs, suggestion: Suggestions
):
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
                    )
                ),
            ],
        ),
    ]


async def build_user_resolution_notification(
    *, user_config: UserConfigs, suggestion: Suggestions
):
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
                    )
                ),
            ],
        ),
    ]


async def build_queued_user_resolution_notification(
    *, user_config: UserConfigs, suggestion: QueuedSuggestions, rest
):
    extra = None
    if suggestion.state == QueuedSuggestionStateEnum.APPROVED:
        related_suggestion: Suggestions = suggestion.related_suggestion
        related_suggestion.guild_configuration = await related_suggestion.get_related(
            Suggestions.guild_configuration
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
                    )
                ),
            ],
        ),
    ]
    if extra is not None:
        data.extend(extra)

    return data
