from typing import cast

import commons
import hikari
import lightbulb

from bot import constants
from bot.localisation import Localisation
from shared.tables import GuildConfigs


class SuggestionMenu:
    @classmethod
    async def handle_interaction(
        cls,
        response_fields: list[
            hikari.interactions.modal_interactions.ModalInteractionTextInputComponent
            | hikari.interactions.modal_interactions.ModalInteractionFileUploadComponent
            | hikari.interactions.modal_interactions.ModalInteractionStringSelectComponent
        ],
        *,
        ctx: lightbulb.components.MenuContext,
        localisations: Localisation,
        guild_config: GuildConfigs,
        event: hikari.ModalInteractionCreateEvent,
    ):
        suggestion_content: str | None = None
        file_ids: list[int] = []
        anonymously: bool = False
        for entry in response_fields:
            if entry.custom_id == "suggestion":
                entry = cast(
                    hikari.interactions.modal_interactions.ModalInteractionTextInputComponent,
                    entry,
                )
                suggestion_content = entry.value

            elif entry.custom_id == "anonymously":
                entry = cast(
                    hikari.interactions.modal_interactions.ModalInteractionStringSelectComponent,
                    entry,
                )
                anonymously = commons.value_to_bool(entry.values[0])

            elif entry.custom_id == "files":
                entry = cast(
                    hikari.interactions.modal_interactions.ModalInteractionFileUploadComponent,
                    entry,
                )
                file_ids = entry.values  # noqa
        pass

    @classmethod
    async def build_suggest_modal(
        cls,
        *,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        localisations: Localisation,
    ):
        components = [
            hikari.impl.LabelComponentBuilder(
                label=localisations.get_localized_string(
                    "commands.suggest.options.suggestion.name", ctx
                ).capitalize(),
                description=localisations.get_localized_string(
                    "commands.suggest.options.suggestion.description", ctx
                ),
                component=hikari.impl.TextInputBuilder(
                    custom_id="suggestion",
                    label="suggestion",
                    style=hikari.TextInputStyle.PARAGRAPH,
                    required=True,
                    min_length=1,
                    max_length=constants.MAX_CONTENT_LENGTH,
                ),
            ),
        ]
        if guild_config.can_have_images_in_suggestions:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label=localisations.get_localized_string(
                        "commands.suggest.options.image.name", ctx
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "commands.suggest.options.image.description", ctx
                    ),
                    component=hikari.impl.FileUploadComponentBuilder(
                        custom_id="files",
                        min_values=1,
                        max_values=5,
                        is_required=False,
                    ),
                )
            )

        if guild_config.can_have_anonymous_suggestions:
            components.append(
                hikari.impl.LabelComponentBuilder(
                    label=localisations.get_localized_string(
                        "commands.suggest.options.anonymously.name", ctx
                    ).capitalize(),
                    description=localisations.get_localized_string(
                        "commands.suggest.options.anonymously.description", ctx
                    ),
                    component=hikari.impl.TextSelectMenuBuilder(
                        custom_id="anonymously",
                        parent=None,
                        options=[
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.suggestion.yes",
                                    ctx,
                                ),
                                value="yes",
                            ),
                            hikari.impl.SelectOptionBuilder(
                                label=localisations.get_localized_string(
                                    "menus.suggestion.no",
                                    ctx,
                                ),
                                value="no",
                                is_default=True,
                            ),
                        ],
                        min_values=1,
                        max_values=1,
                        is_required=False,
                    ),
                )
            )

        return components
