from datetime import timedelta
import commons
import arrow
from commons import timing

from web.tables import GuildTokens
from unittest.mock import AsyncMock
from copy import deepcopy
import logging

import pytest
import stripe
import redis.asyncio as aioredis

from tests.conftest import BaseGiven, GuildTokenT, BaseWhen
from web import constants
from web.util import payments

Given = BaseGiven()

# Minimal object of https://docs.stripe.com/api/subscriptions/object
STRIPE_PRICE_ID_GUILDS_MONTHLY = "TestGuildPriceID"
STRIPE_PRICE_ID_USERS_MONTHLY = "TestUserPriceID"
EXPIRY_DATE = arrow.get(1682288167)  # Date from stripe docs
guild_price_id = {
    "price": {"id": STRIPE_PRICE_ID_GUILDS_MONTHLY},
    "id": "GuildOne",
    "quantity": 1,
    "current_period_end": EXPIRY_DATE.timestamp(),
}
user_price_id = {
    "price": {"id": STRIPE_PRICE_ID_USERS_MONTHLY},
    "id": "UserOne",
    "quantity": 1,
    "current_period_end": EXPIRY_DATE.timestamp(),
}
empty_sub = {"items": {"data": []}}


class PaymentWhen(BaseWhen):
    @staticmethod
    def stripe_subscription_is_patched_with_(
        monkeypatch: pytest.MonkeyPatch, sub_object: dict
    ) -> None:
        mock = AsyncMock()
        mock.return_value = sub_object
        monkeypatch.setattr(stripe.Subscription, "retrieve_async", mock)
        monkeypatch.setattr(
            constants, "STRIPE_PRICE_ID_GUILDS_MONTHLY", STRIPE_PRICE_ID_GUILDS_MONTHLY
        )

    def redis_does_not_contain_paid_invoice(self) -> None:
        # Nothing
        return

    @staticmethod
    def no_guild_tokens_exist() -> None:
        assert GuildTokens().count().run_sync() == 0


When = PaymentWhen()


async def test_existing_subscription(caplog: pytest.LogCaptureFixture) -> None:
    """Tests the handling of duplicate subscription calls."""
    user = Given.user("test@suggestions.gg").object
    Given.x_guild_tokens_exist(GuildTokenT(subscription_id="test", user=user))

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        "Got asked to fulfil guild purchase for 'test' but was already handled"
    ]


async def test_with_no_guild_items(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests fulfil_guild_purchase does nothing unless the its price SKU is purchased."""
    user = Given.user("test@suggestions.gg").object

    When.redis_does_not_contain_paid_invoice()
    test_subscription = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        f"Observed price id '{STRIPE_PRICE_ID_USERS_MONTHLY}' not needing "
        f"to be handled by fulfil_guild_purchase"
    ]


# noinspection DuplicatedCode
async def test_with_one_guild_item(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests fulfil_guild_purchase creates a single subscription for one entry."""
    user = Given.user("test@suggestions.gg").object

    When.redis_does_not_contain_paid_invoice()
    test_subscription = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription "
        f"'test' and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 1


# noinspection DuplicatedCode
async def test_payment_sets_expiry_date(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests fulfil_guild_purchase sets expiry to now if no expiry date has arrived."""
    user = Given.user("test@suggestions.gg").object

    When.redis_does_not_contain_paid_invoice()
    test_subscription = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription "
        f"'test' and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 1
    gt = await GuildTokens().objects().first()
    assert gt is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt.expires_at,
        timedelta(days=6),
    )


# noinspection DuplicatedCode
async def test_with_guild_item_quantity_two(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user("test@suggestions.gg").object

    When.redis_does_not_contain_paid_invoice()
    test_subscription = deepcopy(empty_sub)
    guild_price_id_obj = deepcopy(guild_price_id)
    guild_price_id_obj["quantity"] = 2
    test_subscription["items"]["data"].append(guild_price_id_obj)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        f"Created 2 GuildTokens for subscription "
        f"'test' and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 2


# noinspection DuplicatedCode
async def test_with_two_guild_items(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user("test@suggestions.gg").object

    When.redis_does_not_contain_paid_invoice()
    test_subscription = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    guild_price_id_two = deepcopy(guild_price_id)
    guild_price_id_two["id"] = "GuildTwo"
    test_subscription["items"]["data"].append(guild_price_id_two)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription "
        f"'test' and data 'GuildOne' for user '{user.id} ({user.email})'",
        f"Created 1 GuildTokens for subscription "
        f"'test' and data 'GuildTwo' for user '{user.id} ({user.email})'",
    ]
    assert await GuildTokens().count() == 2
