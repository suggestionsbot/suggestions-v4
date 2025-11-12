import datetime
from unittest.mock import AsyncMock

import hikari
import lightbulb
from freezegun import freeze_time

from shared.tables import GuildConfigs
from shared.tables.mixins.audit import utc_now


async def test_guild_config_default():
    r_1: GuildConfigs = GuildConfigs(id=123)
    assert r_1.id == 123
    assert r_1.keep_logs is False
    assert r_1.dm_messages_disabled is False
    assert r_1.log_channel_id is None
    assert r_1.queued_suggestion_channel_id is None
    assert r_1.queued_suggestion_log_channel_id is None
    assert r_1.threads_for_suggestions is True
    assert r_1.suggestions_channel_id is None
    assert r_1.can_have_anonymous_suggestions is False
    assert r_1.auto_archive_threads is False
    assert r_1.uses_suggestions_queue is False
    assert r_1.virtual_suggestions_queue is True
    assert r_1.can_have_images_in_suggestions is True
    assert r_1.anonymous_resolutions is False
    assert r_1.blocked_users == []
    assert r_1.ping_on_thread_creation is True


@freeze_time("2025-01-20")
def test_premium_is_enabled():
    gc: GuildConfigs = GuildConfigs(id=123)
    r_1: lightbulb.Context = AsyncMock(spec=lightbulb.Context)
    r_1_1: hikari.Entitlement = AsyncMock(spec=hikari.Entitlement)
    r_1_1.is_deleted = True
    r_1.interaction.entitlements = [r_1_1]
    assert gc.premium_is_enabled(r_1) is False

    r_1: lightbulb.Context = AsyncMock(spec=lightbulb.Context)
    r_1_1: hikari.Entitlement = AsyncMock(spec=hikari.Entitlement)
    r_1_1.is_deleted = True
    r_1_2: hikari.Entitlement = AsyncMock(spec=hikari.Entitlement)
    r_1_2.starts_at = datetime.datetime(2025, 1, 18, tzinfo=datetime.timezone.utc)
    r_1_2.ends_at = None
    r_1.interaction.entitlements = [r_1_1, r_1_2]
    assert gc.premium_is_enabled(r_1) is True

    r_1: lightbulb.Context = AsyncMock(spec=lightbulb.Context)
    r_1_1: hikari.Entitlement = AsyncMock(spec=hikari.Entitlement)
    r_1_1.starts_at = None
    r_1_1.ends_at = None
    r_1.interaction.entitlements = [r_1_1]
    assert gc.premium_is_enabled(r_1) is True

    r_1: lightbulb.Context = AsyncMock(spec=lightbulb.Context)
    r_1_1: hikari.Entitlement = AsyncMock(spec=hikari.Entitlement)
    r_1_1.starts_at = None
    r_1_1.ends_at = datetime.datetime(2025, 1, 18, tzinfo=datetime.timezone.utc)
    r_1.interaction.entitlements = [r_1_1]
    assert gc.premium_is_enabled(r_1) is False
