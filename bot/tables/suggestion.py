from enum import Enum

from piccolo.columns import Serial, Varchar, Text, ForeignKey, BigInt, Timestamptz
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from bot.tables import GuildConfig, UserConfig
from bot.tables.mixins import AuditMixin
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
    guild_configuration = ForeignKey(GuildConfig, index=True)
    # Secret as if anon we don't want to reveal
    user_configuration = ForeignKey(UserConfig, index=True, secret=True)
    state = Varchar(
        help_text="The current state of this suggestion", choices=SuggestionStateEnum
    )
    moderator_note = Text(
        null=True,
        required=False,
        help_text="An optional note that was added by a moderator",
    )
    moderator_note_added_by = ForeignKey(UserConfig, index=True)
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
        help_text="If the state is approved or rejected, did they add a message to the closing state?",
    )
    resolved_at = Timestamptz(
        null=True,
        default=None,
        required=False,
        help_text="When this suggestion resolved?",
    )
    image_url = Text(
        null=True,
        default=None,
        required=False,
        help_text="An optional image URL to include in the suggestion embed. "
        "Will usually be a bot managed CF R2 link.",
    )
    author_display_name = Text(
        help_text="How should we display the author? Either name or <Anonymous>",
    )

    @property
    def guild_id(self) -> int:
        return self.guild_configuration.id

    @property
    def author_id(self) -> int:
        return self.user_configuration.id
