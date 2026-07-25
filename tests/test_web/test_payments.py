# ruff: noqa: ARG001
import logging
from copy import deepcopy
from datetime import timedelta
from typing import TypedDict
from unittest.mock import AsyncMock

import arrow
import pytest
import redis.asyncio as aioredis
import stripe
from commons import timing
from freezegun import freeze_time

from tests.conftest import BaseGiven, GuildTokenT, BaseWhen
from web import constants
from web.tables import GuildTokens
from web.util import payments

Given = BaseGiven()

# Minimal object of https://docs.stripe.com/api/subscriptions/object
STRIPE_PRICE_ID_GUILDS_MONTHLY = "TestGuildPriceID"
STRIPE_PRICE_ID_USERS_MONTHLY = "TestUserPriceID"
FROZEN_DATE = arrow.get("2012-01-14")
EXPIRY_DATE = arrow.get("2012-02-14")
BASE_CUSTOMER_EMAIL = "tests@suggestions.gg"
BASE_SUBSCRIPTION_EVENT_ID = "SubscriptionEventID"
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


class DataT(TypedDict):
    data: list


class SubscriptionT(TypedDict):
    items: DataT
    status: str


empty_sub: SubscriptionT = {
    "items": {"data": []},
    "status": "active",
}

# Minimal https://docs.stripe.com/api/events/object
empty_event = {
    "data": {
        "object": {
            "id": BASE_SUBSCRIPTION_EVENT_ID,
            "customer": "CustomerId",  # This is nullable?
        }
    }
}


# Minimal https://docs.stripe.com/api/customers/object
class CustomerT(TypedDict):
    email: str
    id: str


base_customer: CustomerT = {"email": BASE_CUSTOMER_EMAIL, "id": "CustomerId"}


class PaymentWhen(BaseWhen):
    @staticmethod
    def stripe_subscription_is_patched_with_(
        monkeypatch: pytest.MonkeyPatch, sub_object: SubscriptionT
    ) -> None:
        mock = AsyncMock()
        mock.return_value = sub_object
        monkeypatch.setattr(stripe.Subscription, "retrieve_async", mock)
        monkeypatch.setattr(
            constants, "STRIPE_PRICE_ID_GUILDS_MONTHLY", STRIPE_PRICE_ID_GUILDS_MONTHLY
        )

    @staticmethod
    def stripe_customer_is_patched_with_(
        monkeypatch: pytest.MonkeyPatch, customer: CustomerT
    ) -> None:
        mock = AsyncMock()
        mock.return_value = customer
        monkeypatch.setattr(stripe.Customer, "retrieve_async", mock)

    def redis_does_not_contain_paid_invoice(self) -> None:
        # Nothing
        return

    @staticmethod
    def no_guild_tokens_exist() -> None:
        assert GuildTokens().count().run_sync() == 0


When = PaymentWhen()


async def test_existing_subscription(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests the handling of duplicate subscription calls."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.x_guild_tokens_exist(
        GuildTokenT(subscription_id=BASE_SUBSCRIPTION_EVENT_ID, user=user)
    )
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

    assert caplog.messages == [
        f"Got asked to fulfil guild purchase for '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"but was already handled"
    ]


async def test_with_no_guild_items(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests fulfil_guild_purchase does nothing unless the its price SKU is purchased."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    When.redis_does_not_contain_paid_invoice()
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

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
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    When.redis_does_not_contain_paid_invoice()
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription "
        f"'{BASE_SUBSCRIPTION_EVENT_ID}' and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 1


# noinspection DuplicatedCode
async def test_payment_sets_expiry_date(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests fulfil_guild_purchase sets expiry to future if paid."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    When.redis_does_not_contain_paid_invoice()
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription "
        f"'{BASE_SUBSCRIPTION_EVENT_ID}' and data 'GuildOne' for user '{user.id} ({user.email})'"
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
@freeze_time(FROZEN_DATE.datetime)
async def test_payment_sets_expiry_date_when_not_paid(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests fulfil_guild_purchase sets expiry to now if sub is not active."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    When.redis_does_not_contain_paid_invoice()
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["status"] = "unpaid"
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription "
        f"'{BASE_SUBSCRIPTION_EVENT_ID}' and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 1
    gt = await GuildTokens().objects().first()
    assert gt is not None
    assert timing.is_within_next_(
        FROZEN_DATE.datetime,
        gt.expires_at,
        timedelta(days=1),
    )


# noinspection DuplicatedCode
async def test_with_guild_item_quantity_two(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    When.redis_does_not_contain_paid_invoice()
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    guild_price_id_obj = deepcopy(guild_price_id)
    guild_price_id_obj["quantity"] = 2
    test_subscription["items"]["data"].append(guild_price_id_obj)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

    assert caplog.messages == [
        f"Created 2 GuildTokens for subscription "
        f"'{BASE_SUBSCRIPTION_EVENT_ID}' and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 2


# noinspection DuplicatedCode
async def test_with_two_guild_items(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    When.redis_does_not_contain_paid_invoice()
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    guild_price_id_two = deepcopy(guild_price_id)
    guild_price_id_two["id"] = "GuildTwo"
    test_subscription["items"]["data"].append(guild_price_id_two)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event, user=user)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildOne' for user '{user.id} ({user.email})'",
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildTwo' for user '{user.id} ({user.email})'",
    ]
    assert await GuildTokens().count() == 2
