import time
import typing
from enum import Enum

import hikari
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
    And,
    Where,
    OnDelete,
)
from piccolo.columns.indexes import IndexMethod
from piccolo.columns.operators import Equal
from piccolo.table import Table

from bot.localisation import Localisation
from bot.utils.id import generate_id
from shared.saq.worker import SAQ_QUEUE
from shared.tables.mixins import AuditMixin


class QueuedSuggestionStateEnum(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


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
    state_raw = Varchar(
        help_text="The current state of this suggestion",
        choices=QueuedSuggestionStateEnum,
        null=False,
        required=True,
        default=QueuedSuggestionStateEnum.PENDING,
    )
    suggestion = Text(help_text="The actual content of this suggestion")
    guild_configuration = ForeignKey(
        LazyTableReference("GuildConfigs", module_path="shared.tables"),
        index=True,
        on_delete=OnDelete.restrict,
    )
    # Secret as if anon we don't want to reveal
    user_configuration = ForeignKey(
        LazyTableReference("UserConfigs", module_path="shared.tables"),
        index=True,
        secret=True,
        on_delete=OnDelete.restrict,
    )
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
    related_suggestion_id = Text(
        help_text="Migration helpers, to delete later", default=None, null=True
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
    def is_physical(self):
        return self.channel_id is not None and self.message_id is not None

    @property
    def is_anonymous(self) -> bool:
        return self.author_display_name == "Anonymous"

    @property
    def state(self) -> QueuedSuggestionStateEnum:
        return QueuedSuggestionStateEnum(self.state_raw)

    @classmethod
    async def fetch_guild_queued_suggestions(
        cls, guild_id: int, *, still_in_queue: bool
    ) -> list[typing.Self]:
        query = cls.objects(
            QueuedSuggestions.user_configuration,
            QueuedSuggestions.guild_configuration,
            QueuedSuggestions.related_suggestion,
        ).where(
            And(
                Where(
                    QueuedSuggestions.state_raw,
                    QueuedSuggestionStateEnum.PENDING,
                    operator=Equal,
                ),
                Where(
                    QueuedSuggestions.guild_configuration.guild_id,
                    guild_id,
                    operator=Equal,
                ),
            )
        )
        return await query

    # noinspection PyPep8Naming
    @classmethod
    async def fetch_queued_suggestion(
        cls, sID: str, guild_id: int, *, lock_rows: bool = False
    ) -> typing.Self:
        """Simple helper method to also ensure configurations are prefetched"""
        query = cls.objects(
            QueuedSuggestions.user_configuration,
            QueuedSuggestions.guild_configuration,
            QueuedSuggestions.related_suggestion,
        ).where(
            And(
                Where(QueuedSuggestions.sID, sID, operator=Equal),
                Where(
                    QueuedSuggestions.guild_configuration.guild_id,
                    guild_id,
                    operator=Equal,
                ),
            )
        )
        if lock_rows:
            query = query.lock_rows("NO KEY UPDATE", of=(cls,))

        query = query.first()
        return await query

    @property
    def footer_sid(self) -> str:
        # sid_text = f"[{self.sID}](https://dashboard.suggestions.gg/guilds/{self.guild_id}/suggestions/{self.sID})"
        return f"`{self.sID}`"

    @property
    def guild_id(self) -> int:
        return self.guild_configuration.guild_id

    @property
    def author_id(self) -> int:
        return self.user_configuration.user_id

    @property
    def color(self) -> hikari.Color:
        from bot.constants import PENDING_COLOR, APPROVED_COLOR, REJECTED_COLOR

        if self.state == QueuedSuggestionStateEnum.APPROVED:
            return APPROVED_COLOR

        elif self.state == QueuedSuggestionStateEnum.REJECTED:
            return REJECTED_COLOR

        return PENDING_COLOR

    async def notify_users_of_resolution(self):
        """Helper to queue user resolution notifications"""
        await SAQ_QUEUE.enqueue(
            "queued_suggestion_resolved_notifications",
            suggestion_id=self.sID,
            guild_id=self.guild_id,
            scheduled=time.time() + 1,
        )

    async def as_components(
        self,
        rest: hikari.api.RESTClient,
        locale: hikari.Locale | str,
        localisations: Localisation,
        *,
        include_buttons: bool = True,
        paginator_id: str | None = None,
        link_id: str | None = None,
    ) -> list[ContainerComponentBuilder | MessageActionRowBuilder]:
        components: list = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "components.queued_suggestions.suggestion",
                    locale,
                    extras={"SUGGESTION": self.suggestion},
                )
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
                    content=localisations.get_localized_string(
                        "components.queued_suggestions.submitter",
                        locale,
                        extras={"AUTHOR_DISPLAY": self.author_display_name},
                    )
                )
            )

        else:
            user: hikari.User = await rest.fetch_user(self.author_id)  # TODO Cache
            components.append(
                hikari.impl.SectionComponentBuilder(
                    components=[
                        hikari.impl.TextDisplayComponentBuilder(
                            content=localisations.get_localized_string(
                                "components.queued_suggestions.submitter",
                                locale,
                                extras={"AUTHOR_DISPLAY": self.author_display_name},
                            )
                        ),
                    ],
                    accessory=hikari.impl.ThumbnailComponentBuilder(
                        media=user.display_avatar_url,
                    ),
                )
            )

        if self.resolved_by is not None and self.related_suggestion is None:
            # Means it's been rejected so we should show it
            components.append(
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                )
            )
            content = localisations.get_localized_string(
                "components.queued_suggestions.resolved",
                locale,
                extras={
                    "RESOLVED_BY_DISPLAY": self.resolved_by_display_text,
                },
            )
            if self.resolved_note is not None:
                content += localisations.get_localized_string(
                    "components.queued_suggestions.resolved_note",
                    locale,
                    extras={
                        "RESOLVED_BY_NOTE": self.resolved_note,
                    },
                )

            components.append(hikari.impl.TextDisplayComponentBuilder(content=content))

        extras = {
            "SID": self.footer_sid,
            "CREATED": (int(self.created_at.timestamp())),
        }
        if self.resolved_at is not None:
            extras["RESOLVED"] = int(self.resolved_at.timestamp())

        components.append(
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    (
                        "components.queued_suggestions.footer_resolved"
                        if self.state != QueuedSuggestionStateEnum.PENDING
                        else "components.queued_suggestions.footer"
                    ),
                    locale,
                    extras=extras,
                ),
            )
        )

        data: list = [
            hikari.impl.ContainerComponentBuilder(
                accent_color=self.color,
                components=components,
            ),
        ]
        if include_buttons:
            if paginator_id:
                approved = f"v4_queue:approve:{paginator_id}:{self.sID}:{link_id}"
                rejected = f"v4_queue:reject:{paginator_id}:{self.sID}:{link_id}"
            else:
                approved = f"v4_queued_suggestion:approve:{self.sID}"
                rejected = f"v4_queued_suggestion:reject:{self.sID}"

            data.append(
                hikari.impl.MessageActionRowBuilder(
                    components=[
                        hikari.impl.InteractiveButtonBuilder(
                            style=hikari.ButtonStyle.SUCCESS,
                            label=localisations.get_localized_string(
                                "values.suggest.queue_approve", locale
                            ),
                            custom_id=approved,
                        ),
                        hikari.impl.InteractiveButtonBuilder(
                            style=hikari.ButtonStyle.DANGER,
                            label=localisations.get_localized_string(
                                "values.suggest.queue_reject", locale
                            ),
                            custom_id=rejected,
                        ),
                    ]
                )
            )

        return data
