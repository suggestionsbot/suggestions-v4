import typing

import hikari
import lightbulb
from hikari.impl import ContainerComponentBuilder, MessageActionRowBuilder
from piccolo.columns import (
    Serial,
    Varchar,
    Text,
    ForeignKey,
    BigInt,
    Timestamptz,
    Boolean,
    LazyTableReference,
    Array,
)
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from bot.constants import EMBED_COLOR
from bot.localisation import Localisation
from shared.tables import GuildConfigs, UserConfigs
from shared.tables.mixins import AuditMixin
from bot.utils import generate_id


class QueuedSuggestions(Table, AuditMixin):
    id = Serial(
        primary_key=True,
        unique=True,
        index=True,
    )
    sID = Varchar(
        default=generate_id,
        unique=True,
        index=True,
        index_method=IndexMethod.hash,
        help_text="The user facing id. This should be used everywhere.",
    )
    suggestion = Text(help_text="The actual content of this suggestion")
    guild_configuration = ForeignKey(GuildConfigs, index=True)
    # Secret as if anon we don't want to reveal
    user_configuration = ForeignKey(UserConfigs, index=True, secret=True)
    channel_id = BigInt(
        null=True,
        default=None,
        required=False,
        help_text="If this suggestion has been sent to discord, what channel is it in?",
    )
    message_id = BigInt(
        null=True,
        default=None,
        required=False,
        help_text="If this suggestion has been sent to discord, what is it's message id?",
    )
    still_in_queue = Boolean(
        default=True,
        help_text="Is this still in the queue or is it a suggestion now?",
        index=True,
    )
    related_suggestion = ForeignKey(
        LazyTableReference(
            table_class_name="Suggestions",
            app_name="shared",
        ),
        default=None,
        null=True,
        required=False,
        help_text="If this is no longer in the queue, what suggestion is it now?",
    )
    # BigInt vs ForeignKey as moderators dont need configs
    # Secret as if anon we don't want to reveal
    resolved_by = BigInt(
        null=True,
        default=None,
        required=False,
        secret=True,
        help_text="If the state is approved or rejected, who made that call?",
    )
    resolved_by_display_text = Text(
        null=True,
        default=None,
        required=False,
        help_text="How should we display the approver? Either name or <Anonymous>",
    )
    resolved_note = Text(
        null=True,
        default=None,
        required=False,
        help_text="If the state is approved or rejected, did they add a "
        "message to the closing state?",
    )
    resolved_at = Timestamptz(
        null=True,
        default=None,
        required=False,
        help_text="When this suggestion resolved?",
    )
    image_urls = Array(
        base_column=Text(),
        default=[],
        help_text="Optional image URLs to include in the suggestion embed. "
        "Will usually be a bot managed CF R2 link.",
        null=True,
        required=False,
    )
    author_display_name = Text(
        help_text="How should we display the author? Either name or <Anonymous>",
    )

    @property
    def is_anonymous(self) -> bool:
        return self.author_display_name == "Anonymous"

    # noinspection PyPep8Naming
    @classmethod
    async def fetch_queued_suggestion(cls, sID: str) -> typing.Self:
        """Simple helper method to also ensure configurations are prefetched"""
        return await cls.objects(
            QueuedSuggestions.user_configuration, QueuedSuggestions.guild_configuration
        ).get(QueuedSuggestions.sID == sID)

    @property
    def guild_id(self) -> int:
        return self.guild_configuration.guild_id

    @property
    def author_id(self) -> int:
        return self.user_configuration.user_id

    async def as_components(
        self,
        bot: hikari.RESTAware,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        localisations: Localisation,
    ) -> list[ContainerComponentBuilder | MessageActionRowBuilder]:
        # TODO Localize once format decided
        user: hikari.User = await bot.rest.fetch_user(self.author_id)
        components: list = [
            hikari.impl.TextDisplayComponentBuilder(
                content=f"**Suggestion**\n{self.suggestion}"
            ),
        ]
        if self.image_urls:
            items = []
            for entry in self.image_urls:
                items.append(
                    hikari.impl.MediaGalleryItemBuilder(
                        media=entry,
                    ),
                )

            components.append(hikari.impl.MediaGalleryComponentBuilder(items=items))

        components.append(
            hikari.impl.SeparatorComponentBuilder(
                divider=True,
                spacing=hikari.SpacingType.SMALL,
            )
        )
        if self.is_anonymous:
            components.append(
                hikari.impl.TextDisplayComponentBuilder(
                    content=f"**Submitter**\n{self.author_display_name}"
                )
            )

        else:
            components.append(
                hikari.impl.SectionComponentBuilder(
                    components=[
                        hikari.impl.TextDisplayComponentBuilder(
                            content=f"**Submitter**\n{self.author_display_name}"
                        ),
                    ],
                    accessory=hikari.impl.ThumbnailComponentBuilder(
                        media=user.display_avatar_url,
                    ),
                )
            )

        if self.resolved_note and self.resolved_by is not None:
            # Means it's been rejected so we should show it
            components.append(
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                )
            )
            note_desc = (
                f"\n\n**Moderator**\n{self.resolved_by_display_text}"
                f"\n**Moderator note**\n{self.resolved_note}"
            )
            components.append(hikari.impl.TextDisplayComponentBuilder(content=note_desc))

        sid_text = f"`{self.sID}`"
        sid_text = f"[{self.sID}](https://dashboard.suggestions.gg/guilds/{self.guild_id}/queue/{self.sID})"
        components.append(
            hikari.impl.TextDisplayComponentBuilder(
                content=f"Queued Suggestion ID: {sid_text} | Created <t:{int(self.created_at.timestamp())}:R>"
            )
        )
        # components.append(
        #     hikari.impl.SectionComponentBuilder(
        #         accessory=hikari.impl.LinkButtonBuilder(
        #             url=f"https://dashboard.suggestions.gg/guilds/{self.guild_id}/queue/{self.sID}",
        #             label="View in dashboard",
        #         ),
        #         components=[
        #             hikari.impl.TextDisplayComponentBuilder(
        #                 content=f"Queued Suggestion ID: {sid_text} | Created <t:{int(self.created_at.timestamp())}:R>"
        #             ),
        #         ],
        #     ),
        # )

        return [
            hikari.impl.ContainerComponentBuilder(
                accent_color=EMBED_COLOR,
                components=components,
            ),
            hikari.impl.MessageActionRowBuilder(
                components=[
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.SUCCESS,
                        label=localisations.get_localized_string(
                            "values.suggest.queue_approve", ctx
                        ),
                        custom_id="queue_approve",
                    ),
                    hikari.impl.InteractiveButtonBuilder(
                        style=hikari.ButtonStyle.DANGER,
                        label=localisations.get_localized_string(
                            "values.suggest.queue_reject", ctx
                        ),
                        custom_id="queue_reject",
                    ),
                ]
            ),
        ]
