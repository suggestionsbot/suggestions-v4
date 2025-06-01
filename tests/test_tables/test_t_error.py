from bot.tables import InternalErrors


async def test_default_error():
    # Only test defaults
    r_1: InternalErrors = InternalErrors(
        error_name="Test",
        traceback="Boo",
        user_id=1,
        guild_id=2,
        command_name="cmd",
    )
    assert len(r_1.id) == 11
    assert r_1.has_been_fixed is False
