from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import AsyncMock

import disnake
import fakeredis
import pytest
from piccolo.apps.tester.commands.run import set_env_var, refresh_db
from piccolo.conf.apps import Finder
from piccolo.table import create_db_tables, drop_db_tables

from bot import SuggestionsBot


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
    # Setup DB per test
    with set_env_var(var_name="PICCOLO_CONF", temp_value="piccolo_conf_test"):
        refresh_db()
        tables = Finder().get_table_classes()
        # Ensure DB is cleared from any prior hanging tests
        await drop_db_tables(*tables)

        # Set up DB
        await create_db_tables(*tables)
        yield
        await drop_db_tables(*tables)


@pytest.fixture
def redis_client(request) -> fakeredis.FakeAsyncRedis:
    redis_client = fakeredis.FakeAsyncRedis(decode_responses=True)
    return redis_client


@pytest.fixture
def bot(redis_client) -> SuggestionsBot:
    return SuggestionsBot(redis_instance=redis_client)


@pytest.fixture
def fake_interaction(bot) -> AsyncMock:
    """An async mock acting like disnake.Interaction"""
    mock = AsyncMock()
    mock.client = bot
    mock.channel_id = random.randint(1, 10000)
    mock.author.id = random.randint(1, 10000)
    mock.guild_id = random.randint(1, 10000)
    mock.locale = disnake.Locale.en_GB
    mock.id = random.randint(5000, 10000)
    return mock
