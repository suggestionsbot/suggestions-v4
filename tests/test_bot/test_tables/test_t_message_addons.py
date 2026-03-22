import asyncio
import datetime

import arrow
import pytest
from freezegun import freeze_time

from bot.tables import MessageAddons, PossibleMessageAddons
from bot.tables.message_addon import GLOBAL_MESSAGES
from shared.utils import configs


@freeze_time("2025-04-20")
@pytest.mark.parametrize(
    "shown_at,expected_result,message",
    [
        (arrow.get("2025-04-20").datetime, True, "Expected true as was shown today"),
        (
            arrow.get("2025-03-20").datetime,
            True,
            "Expected true as was shown one month ago",
        ),
        (
            arrow.get("2025-02-21").datetime,
            True,
            "Expected true as was shown two months ago",
        ),
        (
            arrow.get("2025-02-19").datetime,
            False,
            "Expected False as was shown over two months ago",
        ),
        (
            arrow.get("2024-02-19").datetime,
            False,
            "Expected False as was shown over two months ago",
        ),
    ],
)
async def test_has_been_shown_message_recently(
    shown_at: datetime.datetime, expected_result, message
):
    user_config = await configs.ensure_user_config(123)
    ma = MessageAddons(
        shown_message=PossibleMessageAddons.READ_CHANGELOG,
        user=user_config,
        shown_at=shown_at,
    )
    await ma.save()
    assert (
        await MessageAddons.has_been_shown_message_recently(user_config)
        == expected_result
    ), message


async def test_get_message_timeframe():
    user_config = await configs.ensure_user_config(123)
    r_1 = await MessageAddons.get_message(user_config)
    assert r_1 is not None
    await asyncio.sleep(1)
    r_2 = await MessageAddons.get_message(user_config)
    assert r_2 is None


@freeze_time("2025-04-20")
async def test_get_message_no_hint():
    user_config = await configs.ensure_user_config(123)
    r_1 = await MessageAddons.get_message(user_config)
    assert r_1 is not None
    assert r_1.shown_message_enum in GLOBAL_MESSAGES


@freeze_time("2025-04-20")
async def test_get_message_hint():
    user_config = await configs.ensure_user_config(123)
    r_1 = await MessageAddons.get_message(
        user_config, hint=PossibleMessageAddons.READ_CHANGELOG
    )
    assert r_1 is not None
    assert r_1.shown_message_enum == PossibleMessageAddons.READ_CHANGELOG
