from bot.tables import GuildConfig


async def test_guild_config_default():
    r_1: GuildConfig = GuildConfig(id=123)
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
