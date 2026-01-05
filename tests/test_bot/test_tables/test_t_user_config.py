from shared.tables import UserConfigs


async def test_user_config_default():
    r_1: UserConfigs = UserConfigs(user_id=123)
    assert r_1.user_id == 123
    assert r_1.dm_messages_disabled is False
    assert r_1.ping_on_thread_creation is True
