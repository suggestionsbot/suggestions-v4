from __future__ import annotations

from pathlib import Path
from typing import Sequence, TypeVar, Type
from unittest import mock

import fakeredis
import hikari
import lightbulb
import pytest
from piccolo.apps.tester.commands.run import set_env_var, refresh_db
from piccolo.conf.apps import Finder
from piccolo.table import create_db_tables, drop_db_tables

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
        yield
        await drop_db_tables(*tables)


@pytest.fixture
def redis_client(request) -> fakeredis.FakeAsyncRedis:
    redis_client = fakeredis.FakeAsyncRedis(decode_responses=True)
    return redis_client


async def prepare_command(
    cls: Type[T],
    options: Sequence[hikari.CommandInteractionOption] = None,
) -> (T, lightbulb.Context):
    await cls.as_command_builder(
        hikari.Locale.EN_GB, lightbulb.localization_unsupported
    )
    client: lightbulb.Client = mock.AsyncMock()
    ctx: lightbulb.Context = mock.AsyncMock(spec=lightbulb.Context, client=client)
    if options is not None:
        ctx.options = options

    cls_instance: T = cls()
    cls_instance._set_context(ctx)  # noqa

    return cls_instance, ctx
