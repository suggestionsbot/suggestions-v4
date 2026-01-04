import typing

import hikari
from piccolo.columns import (
    Serial,
    Varchar,
    Text,
    ForeignKey,
    BigInt,
    Timestamptz,
    Boolean,
    LazyTableReference,
)
from piccolo.columns.indexes import IndexMethod
from piccolo.table import Table

from bot.constants import EMBED_COLOR
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

    async def as_embed(self, bot: hikari.RESTBot | hikari.GatewayBot) -> hikari.Embed:
        user: hikari.User = await bot.rest.fetch_user(self.author_id)

        embed: hikari.Embed = hikari.Embed(
            description=f"**Submitter**\n{self.author_display_name}\n\n"
            f"**Suggestion**\n{self.suggestion}",
            colour=EMBED_COLOR,
            timestamp=self.created_at,
        )
        embed.set_footer(text=f"Queued suggestion ID: {self.sID}")
        if not self.is_anonymous:
            embed.set_thumbnail(user.display_avatar_url)

        if self.image_url:
            embed.set_image(self.image_url)

        if self.resolved_note and self.resolved_by is not None:
            # Means it's been rejected so we should show it
            note_desc = (
                f"\n\n**Moderator**\n{self.resolved_by_display_text}"
                f"\n**Moderator note**\n{self.resolved_note}"
            )
            embed.description += note_desc

        return embed
