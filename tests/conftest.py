from __future__ import annotations

import datetime
from pathlib import Path
from typing import Sequence, TypeVar, Type, Any, Self, AsyncIterator, cast
from unittest import mock
from unittest.mock import AsyncMock, Mock

import httpx
import redis.asyncio as aioredis
import fakeredis
import hikari
import lightbulb
import orjson
import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient
from piccolo.apps.tester.commands.run import set_env_var, refresh_db
from piccolo.conf.apps import Finder
from piccolo.table import create_db_tables, drop_db_tables
from piccolo.testing import ModelBuilder
from piccolo.utils.sync import run_sync

from bot.localisation import Localisation
from shared.saq.worker import SAQ_QUEUE
from web.controllers import AuthController, oauth_controller
from web.tables import APIToken, Users, OAuthEntry
from web import constants as w_constants

T = TypeVar("T")


@pytest.fixture(autouse=True)
def change_test_dir(request, monkeypatch):
    """Ensure all tests run from the base project directory"""
    base_dir = Path(request.fspath).parent.parent
    if base_dir.name == "tests":
        # Handle double nested
        base_dir = base_dir.parent

    monkeypatch.chdir(base_dir)


@pytest.fixture(scope="function", autouse=True)
async def configure_testing():
    # Due to the complexity of tables,
    #   tests can only run with a postgres db present

    # Setup DB per test
    with set_env_var(var_name="PICCOLO_CONF", temp_value="piccolo_conf_test"):
        refresh_db()
        tables = Finder().get_table_classes()
        # Ensure DB is cleared from any prior hanging tests
        await drop_db_tables(*tables)

        # Set up DB
        await create_db_tables(*tables)


@pytest.fixture
def context() -> lightbulb.Context:
    client: lightbulb.Client = mock.AsyncMock()
    ctx: lightbulb.Context = mock.AsyncMock(spec=lightbulb.Context, client=client)
    ctx.interaction.locale = "en-GB"
    return ctx


@pytest.fixture(scope="module")
def localisation(request) -> Localisation:
    base_dir = Path(request.fspath).parent
    if base_dir.name != "tests":
        base_dir = base_dir.parent
    if base_dir.name != "tests":
        base_dir = base_dir.parent
    return Localisation(base_dir / "../bot")


class CustomFakedRedis:
    """Because Async FakeRedis played SO badly."""

    def __init__(self):
        self._redis_client = fakeredis.FakeRedis()

    async def setex(self, name, time, value):
        return self._redis_client.setex(name, time, value)

    async def get(self, name):
        return self._redis_client.get(name)

    async def set(self, name, value, ex=None):
        return self._redis_client.set(name, value, ex=ex)

    async def delete(self, *names):
        return self._redis_client.delete(*names)

    async def flushdb(self, asynchronous: bool = False):
        return self._redis_client.flushdb(asynchronous=asynchronous)


@pytest.fixture(scope="function")
async def redis_client(monkeypatch) -> aioredis.Redis:
    redis_client = CustomFakedRedis()
    await redis_client.flushdb()
    monkeypatch.setattr(w_constants, "REDIS_CLIENT", redis_client)
    return cast(aioredis.Redis, cast(object, redis_client))


@pytest.fixture(scope="function")
def patch_saq(monkeypatch) -> AsyncMock:
    saq_enqueue = AsyncMock()
    monkeypatch.setattr(SAQ_QUEUE, "enqueue", saq_enqueue)
    return saq_enqueue


class AsyncContextManagerMock:
    """Mock for async context managers with nested mocking capabilities."""

    # https://dzone.com/articles/mastering-async-context-manager-mocking-in-python

    def __init__(self, mock):
        """Initialize with a mock that will be returned from __aenter__."""
        self.mock = mock

    async def __aenter__(self):
        """Enter async context manager."""
        return self.mock

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context manager."""
        pass

    def request(self, *args, **kwargs):
        """Return mock to support chaining."""
        return self.mock


@pytest.fixture(scope="function")
def patch_discord_get(monkeypatch, redis_client) -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    get_httpx_client_mock = AsyncContextManagerMock(client)
    monkeypatch.setattr(
        oauth_controller.DISCORD_OAUTH,
        "get_httpx_client",
        lambda: get_httpx_client_mock,
    )
    # client.get = BaseWhen._patched_discord_get
    return client


@pytest.fixture(scope="function")
async def test_client() -> AsyncIterator[AsyncTestClient[Litestar]]:
    from app import app, session_config

    async with AsyncTestClient(app=app, session_config=session_config) as client:
        yield client


async def prepare_command(
    cls: Type[T],
    localisations: Localisation,
    options: Sequence[hikari.CommandInteractionOption] = None,
) -> (T, lightbulb.Context):
    await cls.as_command_builder(hikari.Locale.EN_GB, localisations.lightbulb_provider)
    client: lightbulb.Client = mock.AsyncMock()
    ctx: lightbulb.Context = mock.AsyncMock(spec=lightbulb.Context, client=client)
    ctx.interaction.locale = "en-GB"
    if options is not None:
        ctx.options = options

    cls_instance: T = cls()
    cls_instance._set_context(ctx)  # noqa
    await cls_instance._resolve_options()

    return cls_instance, ctx


class BaseGiven:
    data: dict[str, Any] = {}

    def user(
        self,
        email: str,
        *,
        admin: bool = False,
        superuser: bool = False,
        active: bool = True,
    ) -> Self:
        if not Users.objects().get(Users.email == email).run_sync():
            self.data["user"] = run_sync(
                ModelBuilder.build(
                    Users,
                    {
                        Users.username: email,
                        Users.email: email,
                        Users.admin: admin,
                        Users.active: active,
                        Users.superuser: superuser,
                    },
                )
            )
            run_sync(
                ModelBuilder.build(
                    OAuthEntry,
                    {
                        OAuthEntry.user: self.data["user"],
                        OAuthEntry.provider: "discord",
                        OAuthEntry.last_login: None,
                        OAuthEntry.access_token_raw: w_constants.ENCRYPTION_PROVIDER.encrypt(
                            "fake-access-token"
                        ),
                        OAuthEntry.refresh_token_raw: w_constants.ENCRYPTION_PROVIDER.encrypt(
                            "fake-refresh-token"
                        ),
                        OAuthEntry.oauth_email: email,
                    },
                )
            )
        else:
            self.data["user"] = Users.objects().get(Users.email == email).run_sync()
        return self

    @property
    def object(self) -> Users:
        return self.data["user"]

    @property
    def session_cookie(self) -> str:
        assert "user" in self.data, "Given must have called user first"
        return run_sync(AuthController.create_session_for_user(self.data["user"]))

    @property
    def api_token(self) -> APIToken:
        return run_sync(
            APIToken.create_api_token(
                self.data["user"],
                datetime.timedelta(hours=2),
                datetime.timedelta(days=1),
            )
        )

    def csrf_token(self, test_client: AsyncTestClient[Litestar]) -> str:
        resp = run_sync(test_client.get("/"))
        return resp.cookies["csrf_token"]


class BaseWhen:
    data: dict[str, Any] = {}

    def __init__(self):
        self.data = {}

    @property
    def db(self) -> Self:
        return self

    @property
    def user_discord_oauth(self) -> Self:
        return self

    def bot_is_in_guild(self, guild_id: int, redis: aioredis.Redis) -> Self:
        run_sync(redis.set(f"bot:guilds:is_in:{guild_id}", orjson.dumps(guild_id)))
        return self

    async def _patched_discord_get(self, url: str, **kwargs: Any) -> Mock:
        data = Mock()
        if url == "https://discord.com/api/v10/users/@me/guilds":
            data.status_code = 200
            data.json.return_value = self.data.get("users/@me/guilds", [])
            return data

        elif url == "https://discord.com/api/users/@me":
            data.status_code = 200
            data.json.return_value = self.data["users/@me"]
            return data

        raise ValueError("Missing mocked route")

    def patches_discord_get_requests(self, client):
        client.get = self._patched_discord_get

    def has_profile(
        self,
        _id: int = 271612318947868673,
        *,
        username: str = "skelmis",
        global_name: str = "Skelmis",
        email: str = "testing@suggestions.gg",
    ) -> Self:
        self.data["users/@me"] = {
            "id": str(_id),
            "username": username,
            "avatar": "dfec0a7fbdd5028c7cb617ae738fb9cd",
            "discriminator": "0",
            "public_flags": 256,
            "flags": 256,
            "banner": None,
            "accent_color": 0,
            "global_name": global_name,
            "avatar_decoration_data": None,
            "collectibles": None,
            "display_name_styles": None,
            "banner_color": "#000000",
            "clan": None,
            "primary_guild": None,
            "mfa_enabled": True,
            "locale": "en-GB",
            "premium_type": 0,
            "email": email,
            "verified": True,
        }
        return self

    def contains_guild(self, guild_id: int, *, permissions: int = 1095564657024577) -> Self:
        if "users/@me/guilds" not in self.data:
            self.data["users/@me/guilds"] = []

        # Stripped back to only the data we actually care about
        self.data["users/@me/guilds"].append(
            {
                "id": str(guild_id),
                "name": "10tons",
                "icon": "6fd4fd4e2825077ea5a62bfea88b4098",
                "banner": "48a0dca9a28cff6b3badc213b1329053",
                "owner": False,
                # Unsure on perms but it aint admin or manage server thats for sure
                "permissions": f"{permissions}",
            }
        )

        return self
