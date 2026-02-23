import io
import typing
from enum import Enum

import hikari
import lightbulb
from hikari.impl import ContainerComponentBuilder, MessageActionRowBuilder
from piccolo.columns import Serial, Varchar, Text, ForeignKey, BigInt, Timestamptz, Array
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from bot import constants
from bot.constants import REJECTED_COLOR, APPROVED_COLOR, PENDING_COLOR
from bot.localisation import Localisation
from shared.saq.worker import SAQ_QUEUE
from shared.tables import (
    GuildConfigs,
    UserConfigs,
)
from shared.tables.mixins import AuditMixin
from bot.utils import generate_id


class SuggestionStateEnum(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CLEARED = "Cleared"


class Suggestions(Table, AuditMixin):
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
    state_raw = Varchar(
        help_text="The current state of this suggestion",
        choices=SuggestionStateEnum,
        null=False,
        required=True,
    )
    moderator_note = Text(
        null=True,
        required=False,
        help_text="An optional note that was added by a moderator",
    )
    moderator_note_added_by = ForeignKey(UserConfigs, index=True, secret=True)
    moderator_note_added_by_display_text = Text(
        null=True,
        default=None,
        required=False,
        help_text="How should we display the moderator who added the note? "
        "Either name or <Anonymous>",
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
    thread_id = BigInt(
        null=True,
        default=None,
        required=False,
        help_text="If a thread was automatically created for this suggestion, what was it?",
    )
    # BigInt vs ForeignKey as we moderators dont need configs
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
    def state(self) -> SuggestionStateEnum:
        return SuggestionStateEnum(self.state_raw)

    @property
    def color(self) -> hikari.Color:
        if self.state is SuggestionStateEnum.REJECTED:
            return REJECTED_COLOR

        elif self.state is SuggestionStateEnum.APPROVED:
            return APPROVED_COLOR

        return PENDING_COLOR

    # noinspection PyPep8Naming
    @classmethod
    async def fetch_suggestion(cls, sID: str) -> typing.Self:
        """Simple helper method to also ensure configurations are prefetched"""
        return await cls.objects(
            Suggestions.user_configuration, Suggestions.guild_configuration
        ).get(Suggestions.sID == sID)

    @property
    def guild_id(self) -> int:
        return self.guild_configuration.guild_id

    @property
    def author_id(self) -> int:
        return self.user_configuration.user_id

    @property
    def is_anonymous(self) -> bool:
        return self.author_display_name == "Anonymous"

    async def queue_message_edit(self):
        """Helper to queue the update of the message in discord"""
        from shared.saq.suggestions import queue_suggestion_edit

        await queue_suggestion_edit(suggestion_id=self.sID)

    async def as_components(
        self,
        rest: hikari.api.RESTClient,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        localisations: Localisation,
        *,
        exclude_buttons: bool = False,
        exclude_votes: bool = False,
        use_guild_locale: bool = False,
        guild_config=None,
    ) -> list[ContainerComponentBuilder | MessageActionRowBuilder]:
        user: hikari.User = await rest.fetch_user(self.author_id)
        components: list = [
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "components.suggestions.suggestion",
                    ctx,
                    extras={"SUGGESTION": self.suggestion},
                    use_guild_locale=use_guild_locale,
                    guild_config=guild_config,
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
                        "components.suggestions.submitter",
                        ctx,
                        extras={"AUTHOR_DISPLAY": self.author_display_name},
                        use_guild_locale=use_guild_locale,
                        guild_config=guild_config,
                    )
                )
            )

        else:
            components.append(
                hikari.impl.SectionComponentBuilder(
                    components=[
                        hikari.impl.TextDisplayComponentBuilder(
                            content=localisations.get_localized_string(
                                "components.suggestions.submitter",
                                ctx,
                                extras={"AUTHOR_DISPLAY": self.author_display_name},
                                use_guild_locale=use_guild_locale,
                                guild_config=guild_config,
                            )
                        ),
                    ],
                    accessory=hikari.impl.ThumbnailComponentBuilder(
                        media=user.display_avatar_url,
                    ),
                )
            )

        if self.moderator_note:
            components.append(
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                )
            )
            content = localisations.get_localized_string(
                "components.suggestions.moderator_note",
                ctx,
                extras={
                    "MODERATOR_NOTE_BY_DISPLAY": self.moderator_note_added_by_display_text,
                    "MODERATOR_NOTE": self.moderator_note,
                },
                use_guild_locale=use_guild_locale,
                guild_config=guild_config,
            )
            components.append(hikari.impl.TextDisplayComponentBuilder(content=content))

        if self.state is not SuggestionStateEnum.PENDING:
            components.append(
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                )
            )
            content = localisations.get_localized_string(
                "components.suggestions.resolved",
                ctx,
                extras={
                    "RESOLVED_BY_DISPLAY": self.resolved_by_display_text,
                },
                use_guild_locale=use_guild_locale,
                guild_config=guild_config,
            )
            if self.resolved_note is not None:
                content += localisations.get_localized_string(
                    "components.suggestions.resolved_note",
                    ctx,
                    extras={
                        "RESOLVED_BY_NOTE": self.resolved_note,
                    },
                    use_guild_locale=use_guild_locale,
                    guild_config=guild_config,
                )

            components.append(hikari.impl.TextDisplayComponentBuilder(content=content))

        if not exclude_votes:
            components.append(
                hikari.impl.SeparatorComponentBuilder(
                    divider=True,
                    spacing=hikari.SpacingType.SMALL,
                )
            )
            votes = io.StringIO()
            from shared.tables import SuggestionVotes, SuggestionsVoteTypeEnum

            up_votes = (
                await SuggestionVotes.count()
                .where(SuggestionVotes.suggestion == self)
                .where(SuggestionVotes.vote_type == SuggestionsVoteTypeEnum.UpVote)
            )
            votes.write(f"{constants.DEFAULT_UP_VOTE.mention}: **{up_votes}**\n")

            down_votes = (
                await SuggestionVotes.count()
                .where(SuggestionVotes.suggestion == self)
                .where(SuggestionVotes.vote_type == SuggestionsVoteTypeEnum.DownVote)
            )
            votes.write(f"{constants.DEFAULT_DOWN_VOTE.mention}: **{down_votes}**")

            components.append(
                hikari.impl.TextDisplayComponentBuilder(
                    content=localisations.get_localized_string(
                        "components.suggestions.results",
                        ctx,
                        extras={
                            "VOTES": votes.getvalue(),
                        },
                        use_guild_locale=use_guild_locale,
                        guild_config=guild_config,
                    )
                )
            )

        sid_text = f"`{self.sID}`"
        # sid_text = f"[{self.sID}](https://dashboard.suggestions.gg/guilds/{self.guild_id}/suggestions/{self.sID})"
        components.append(
            hikari.impl.TextDisplayComponentBuilder(
                content=localisations.get_localized_string(
                    "components.suggestions.footer",
                    ctx,
                    extras={
                        "SID": sid_text,
                        "TIMESTAMP": int(self.created_at.timestamp()),
                    },
                    use_guild_locale=use_guild_locale,
                    guild_config=guild_config,
                ),
            )
        )

        result: list = [
            hikari.impl.ContainerComponentBuilder(
                accent_color=self.color,
                components=components,
            ),
        ]
        if not exclude_buttons:
            result.append(
                hikari.impl.MessageActionRowBuilder(
                    components=[
                        hikari.impl.InteractiveButtonBuilder(
                            style=hikari.ButtonStyle.SECONDARY,
                            emoji=constants.DEFAULT_UP_VOTE,
                            custom_id=f"v4_suggestions_up_vote:{self.sID}",
                        ),
                        hikari.impl.InteractiveButtonBuilder(
                            style=hikari.ButtonStyle.SECONDARY,
                            emoji=constants.DEFAULT_DOWN_VOTE,
                            custom_id=f"v4_suggestions_down_vote:{self.sID}",
                        ),
                    ]
                )
            )

        return result
