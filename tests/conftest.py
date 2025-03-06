from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from collections.abc import AsyncIterator

import pytest

from piccolo.apps.tester.commands.run import set_env_var, refresh_db
from piccolo.conf.apps import Finder
from piccolo.table import create_db_tables, drop_db_tables



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


