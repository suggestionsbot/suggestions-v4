import hikari

from bot.constants import LOCALISATIONS


def build_user_resolution_notification():
    return [
        hikari.impl.ContainerComponentBuilder(
            accent_color=hikari.Color.from_hex_code("#C34949"),
            components=[
                hikari.impl.TextDisplayComponentBuilder(
                    content=LOCALISATIONS.get_localized_string()
                ),
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                ),
                hikari.impl.SectionComponentBuilder(
                    accessory=hikari.impl.ThumbnailComponentBuilder(
                        media="",
                    ),
                    components=[
                        hikari.impl.TextDisplayComponentBuilder(
                            content="Always scream into the void before you vanish."
                        ),
                    ],
                ),
                hikari.impl.TextDisplayComponentBuilder(
                    content="They said I couldn't sing opera, so I went to a parallel universe and became a alien."
                ),
            ],
        ),
    ]
