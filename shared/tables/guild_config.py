from __future__ import annotations
import logging
from typing import TYPE_CHECKING, cast

import datetime

import humanize
import orjson
from cooldowns import Cooldown, CallableOnCooldown

import hikari
import lightbulb
from piccolo.columns import (
    BigInt,
    Boolean,
    Array,
    ForeignKey,
    LazyTableReference,
    Text,
    JSON,
)
from piccolo.table import Table

from shared.tables.mixins import AuditMixin
from shared.tables.mixins.audit import utc_now
from web.constants import REDIS_CLIENT
from bot import utils
from bot.constants import (
    LOCALISATIONS,
    ErrorCode,
    ENABLE_FREE_GUILD_PREMIUM,
    user_cooldown_bucket,
    OTEL_TRACER,
)

if TYPE_CHECKING:
    from shared.tables import UserConfigs

logger = logging.getLogger(__name__)


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
    generic_dm_messages_disabled = Boolean(
        default=False,
        help_text="If True, don't send generic messages to members of this guild"
        " such as on suggestion create or resolve",
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
        help_text="A channel the bot can send updates to about new features, "
        "supported languages, etc",
    )
    can_have_anonymous_suggestions = Boolean(
        default=True,
        help_text="Is this guild allowed to make suggestions anonymously?",
    )
    auto_archive_threads = Boolean(
        default=True,
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
    allow_anonymous_moderators = Boolean(
        default=False,
        help_text="If True, moderators can be anonymous when suggestions "
        "are resolved or when adding notes",
    )
    blocked_users = Array(
        BigInt(),
        help_text="A list of users who cannot make suggestions",
    )
    blocked_users_json = JSON(
        help_text="A migration helper given Apache hop doesnt like arrays. "
        "Will need to do a second migration later",
        null=True,
        default=None,
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
    premium = ForeignKey(
        LazyTableReference(
            table_class_name="PremiumGuildConfigs",
            app_name="shared",
        ),
        index=True,
    )

    @property
    def primary_language(self) -> hikari.Locale:
        return hikari.Locale(self.primary_language_raw)

    async def ensure_config_is_setup(
        self,
        *,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        locale: hikari.Locale,
        skip_log_channel_check: bool = False,
    ) -> bool:
        """Returns true if the user was informed the guild still requires setup."""
        has_suggestion_channel: bool = self.suggestions_channel_id is not None
        has_log_channel: bool = skip_log_channel_check or self.log_channel_id is not None
        if self.keep_logs:
            # dont need a log channel with keep logs
            has_log_channel = True

        if has_suggestion_channel and has_log_channel:
            return False

        await ctx.respond(
            embed=utils.error_embed(
                title=LOCALISATIONS.get_localized_string(
                    "errors.requires_setup.title", locale
                ),
                description=LOCALISATIONS.get_localized_string(
                    "errors.requires_setup.description", locale
                ),
                error_code=ErrorCode.BOT_NOT_CONFIGURED,
            ),
            ephemeral=True,
        )
        return True

    async def premium_is_enabled(self) -> bool:
        """Returns true if this guild is considered to have active premium."""
        from web.tables import GuildTokens

        if ENABLE_FREE_GUILD_PREMIUM:
            return True

        return await GuildTokens.does_guild_have_premium(self.guild_id)

    async def run_custom_suggestion_cooldown_check(
        self,
        ctx: lightbulb.Context | lightbulb.components.MenuContext,
        user_config: UserConfigs,
    ) -> bool:
        """Handles a custom suggestion.

        Returns
        -------
        bool
            True if the user is on cooldown and has been told as such

        """
        assert self.premium is not None
        if self.premium.cooldown_amount is None:
            # No custom cooldown to do
            return False

        return_value = False
        redis_key = f"premium:custom_cooldown:{self.guild_id}"
        redis_state = await REDIS_CLIENT.get(redis_key)
        from shared.tables.premium_guild_config import CooldownPeriod

        cooldown = Cooldown(
            self.premium.cooldown_amount,
            CooldownPeriod(self.premium.cooldown_period).as_timedelta(),
            bucket=user_cooldown_bucket,
        )
        if redis_state is not None and redis_state:
            cooldown.load_from_state(orjson.loads(redis_state))

        try:
            await cooldown.increment(ctx.interaction)
        except CallableOnCooldown as exception:
            link_id = await utils.otel.generate_trace_link_state()
            otel_ctx = await utils.otel.get_context_from_link_state(link_id)

            with OTEL_TRACER.start_as_current_span(
                "premium cooldown handler",
                otel_ctx,
            ) as error_span:
                from bot.tables import InternalErrors

                internal_error: InternalErrors = await InternalErrors.persist_error(
                    exception,
                    command_name="Suggestion Creation",
                    guild_id=cast("int", ctx.interaction.guild_id),
                    user_id=ctx.interaction.user.id,
                    extra_info="Premium cooldown hit",
                )
                error_span.set_attribute("error.id", internal_error.id)
                error_span.set_attribute("error.name", internal_error.error_name)
                error_span.set_attribute("error.handled", value=True)
                logger.debug(
                    "CallableOnCooldown for premium cooldown",
                    extra={
                        "interaction.guild.id": ctx.interaction.guild_id,
                        "interaction.user.id": ctx.interaction.user.id,
                        "interaction.user.global_name": ctx.interaction.user.global_name,  # noqa: E501
                        "error.code": ErrorCode.COMMAND_ON_COOLDOWN.value,
                    },
                )
                natural_time = humanize.naturaldelta(exception.retry_after)

                await ctx.respond(
                    embed=utils.error_embed(
                        LOCALISATIONS.get_localized_string(
                            "errors.on_premium_cooldown.title",
                            user_config.primary_language,
                        ),
                        LOCALISATIONS.get_localized_string(
                            "errors.on_premium_cooldown.description",
                            user_config.primary_language,
                            extras={"TIME": natural_time},
                        ),
                        internal_error_reference=internal_error,
                    ),
                    ephemeral=True,
                )
                return_value = True

        await REDIS_CLIENT.set(
            redis_key,
            orjson.dumps(cooldown.get_state()),
            # Expire after two months as we support up to
            # a month so this will keep it clean
            ex=int(datetime.timedelta(days=60).total_seconds()),
        )
        del cooldown
        return return_value
