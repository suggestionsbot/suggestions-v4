import hikari
import lightbulb
from piccolo.columns import BigInt, Boolean, Array, ForeignKey, LazyTableReference, Text
from piccolo.table import Table

from shared.tables import PremiumGuildConfigs
from shared.tables.mixins import AuditMixin
from shared.tables.mixins.audit import utc_now


class GuildConfigs(AuditMixin, Table):
    guild_id = BigInt(
        unique=True,
        index=True,
        help_text="The discord guild id",
    )
    keep_logs = Boolean(
        default=False,
        help_text="Should resolved suggestions stay in the suggestions channel?",
    )
    dm_messages_disabled = Boolean(
        default=False,
        help_text="If True, don't send messages to members of this guild",
    )
    log_channel_id = BigInt(
        default=None,
        null=True,
        help_text="The channel to send resolved suggestions to",
    )
    queued_suggestion_channel_id = BigInt(
        default=None,
        null=True,
        help_text="The channel to send queued suggestions to",
    )
    queued_suggestion_log_channel_id = BigInt(
        default=None,
        null=True,
        help_text="The channel to send rejected queued suggestions to",
    )
    threads_for_suggestions = Boolean(
        default=True,
        help_text="If True, create a thread on new suggestions",
    )
    suggestions_channel_id = BigInt(
        default=None,
        null=True,
        help_text="The channel to send suggestions to",
    )
    update_channel_id = BigInt(
        default=None,
        null=True,
        help_text="A channel the bot can send updates to about new features, supported languages, etc",
    )
    can_have_anonymous_suggestions = Boolean(
        default=True,
        help_text="Is this guild allowed to make suggestions anonymously?",
    )
    auto_archive_threads = Boolean(
        default=False,
        help_text="Auto archive threads when suggestions are resolved?",
    )
    uses_suggestion_queue = Boolean(
        default=False,
        help_text="If True, suggestions go to a queue for review instead "
        "of to the suggestions channel",
    )
    virtual_suggestions_queue = Boolean(
        default=True, help_text="If True, the suggestions queue is virtual"
    )
    can_have_images_in_suggestions = Boolean(
        default=True,
        help_text="If True, users are allowed to add images to suggestions",
    )
    anonymous_resolutions = Boolean(
        default=False,
        help_text="If True, moderators will be anonymous when suggestions are resolved",
    )
    blocked_users = Array(
        BigInt(),
        help_text="A list of users who cannot make suggestions",
    )
    ping_on_thread_creation = Boolean(
        default=True,
        help_text="Ping the suggestions author in the suggestions thread",
    )
    primary_language_raw = Text(
        default=hikari.Locale.EN_GB.value,
        choices=hikari.Locale,
        help_text="The language to use when translating non ephemeral messages",
    )
    premium: PremiumGuildConfigs = ForeignKey(
        LazyTableReference(
            table_class_name="PremiumGuildConfigs",
            app_name="shared",
        ),
        index=True,
    )

    @property
    def primary_language(self) -> hikari.Locale:
        return hikari.Locale(self.primary_language_raw)

    @property
    def primary_language_as_word(self) -> str:
        return {
            "bg": "Bulgarian",
            "cs": "Czech",
            "da": "Danish",
            "de": "German",
            "el": "Greek",
            "en-GB": "English, UK",
            "en-US": "English, US",
            "es-ES": "Spanish",
            "es-419": "Spanish, LATAM",
            "fi": "Finnish",
            "fr": "French",
            "hi": "Hindi",
            "hr": "Croatian",
            "hu": "Hungarian",
            "id": "Indonesian",
            "it": "Italian",
            "ja": "Japanese",
            "ko": "Korean",
            "lt": "Lithuanian",
            "nl": "Dutch",
            "no": "Norwegian",
            "pl": "Polish",
            "pt-BR": "Portuguese, Brazilian",
            "ro": "Romanian",
            "ru": "Russian",
            "sv-SE": "Swedish",
            "th": "Thai",
            "tr": "Turkish",
            "uk": "Ukrainian",
            "vi": "Vietnamese",
            "zh-CN": "Chinese, China",
            "zh-TW": "Chinese, Taiwan",
        }[self.primary_language_raw]

    async def premium_is_enabled(
        self, ctx: lightbulb.Context | lightbulb.components.MenuContext
    ) -> bool:
        """Returns true if this guild is considered to have active premium"""
        # TODO Needs reworking now stripe exists
        return False
        now = utc_now()
        for entitlement in ctx.interaction.entitlements:
            if entitlement.is_deleted is True:
                continue

            if entitlement.starts_at is not None and now < entitlement.starts_at:
                continue

            if entitlement.ends_at is not None and now >= entitlement.ends_at:
                continue

            return True

        return False
