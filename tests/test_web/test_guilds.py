import typing as t

import redis.asyncio as aioredis
import httpx
import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient
from piccolo.utils.sync import run_sync

from tests.conftest import BaseGiven, BaseWhen

Given = BaseGiven()
When = BaseWhen()


class Then:
    data: dict[str, t.Any] = {}

    async def make_get_request(self, route: str) -> httpx.Response:
        resp = await self.data["test_client"].get(
            route,
            cookies={
                "id": self.data["session_cookie"],
            },
            follow_redirects=False,
        )
        return resp


@pytest.mark.parametrize(
    "route,expected_status,dashboard_admin,message",
    [
        ("/guilds", 200, False, "Expected all users to be able to view their guilds"),
        (
            "/guilds/12345/generate_invite",
            403,
            False,
            "Didnt expect users in the guild to be able to invite the bot",
        ),
        (
            "/guilds/12345/test/onboarding",
            403,
            False,
            "Expected non guild members to be barred from guild viewing",
        ),
        (
            "/guilds/12345/test/settings",
            403,
            False,
            "Expected non guild members to be barred from guild viewing",
        ),
        (
            "/guilds/12345/test",
            403,
            False,
            "Expected non guild members to be barred from guild viewing",
        ),
        (
            "/guilds/12345/test/onboarding",
            302,
            True,
            "Expected dashboard admins to be able to view guild",
        ),
        (
            "/guilds/12345/test/settings",
            302,
            True,
            "Expected dashboard admins to be able to view guild",
        ),
        (
            "/guilds/12345/test",
            200,
            True,
            "Expected dashboard admins to be able to view guild",
        ),
    ],
)
async def test_guild_access_as_non_guild_member(
    test_client: AsyncTestClient[Litestar],
    patch_saq,
    patch_discord_get,
    route: str,
    expected_status: int,
    dashboard_admin: bool,
    message: str,
    redis_client: aioredis.Redis,
):
    """Tests if non guild members can access items"""
    session_cookie = Given.user(
        "test@suggestions.gg", admin=dashboard_admin
    ).session_cookie
    When.bot_is_in_guild(12345, redis_client)
    When.patches_discord_get_requests(patch_discord_get)
    When.user_discord_oauth.has_profile()
    When.user_discord_oauth.contains_guild(123)

    then = Then()
    then.data["test_client"] = test_client
    then.data["session_cookie"] = session_cookie
    resp = await then.make_get_request(route)
    assert resp.status_code == expected_status, message
