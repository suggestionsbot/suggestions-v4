from bot.tables import Error


async def test_default_error():
    # Only test defaults
    r_1: Error = Error(
        error_name="Test",
        traceback="Boo",
        user_id=1,
        guild_id=2,
        shard_id=3,
        cluster_id=4,
        command_name="cmd",
    )
    assert len(r_1.id) == 11
    assert r_1.has_been_fixed is False
