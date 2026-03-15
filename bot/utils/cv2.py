import hikari

from bot.constants import LOCALISATIONS, EMBED_COLOR
from shared.tables import UserConfigs, Suggestions


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
