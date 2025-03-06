from bot.tables import UserConfig


async def test_defaults():
    r_1: UserConfig = UserConfig(id=123)
    assert r_1.id == 123
    assert r_1.dm_messages_disabled is False
    assert r_1.ping_on_thread_creation is True
