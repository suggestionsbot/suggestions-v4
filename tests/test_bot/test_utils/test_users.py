# ruff: noqa: CPY001
from unittest.mock import AsyncMock

import hikari

from bot.utils.users import fetch_user_avatar


async def test_missing_user_avatar_is_cached(redis_client: object) -> None:  # noqa: ARG001
    rest = AsyncMock()
    rest.fetch_user.side_effect = hikari.NotFoundError(
        "https://discord.com/api/v10/users/1", {}, b""
    )

    assert await fetch_user_avatar(1, rest=rest) is None
    assert await fetch_user_avatar(1, rest=rest) is None
    rest.fetch_user.assert_awaited_once_with(1)
