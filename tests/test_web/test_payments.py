# ruff: noqa: ARG001
from operator import gt
import logging
from copy import deepcopy
from datetime import timedelta
from typing import TypedDict, Literal, Final
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

QUANTITY_OF_ONE: Final = 1
QUANTITY_OF_TWO: Final = 2
STRIPE_PRICE_ID_GUILDS_MONTHLY = "TestGuildPriceID"
STRIPE_PRICE_ID_USERS_MONTHLY = "TestUserPriceID"
FROZEN_DATE = arrow.get("2012-01-14")
EXPIRY_DATE = arrow.get("2012-02-14")
BASE_CUSTOMER_EMAIL = "tests@suggestions.gg"
BASE_SUBSCRIPTION_EVENT_ID = "SubscriptionEventID"
guild_price_id = {
    "price": {"id": STRIPE_PRICE_ID_GUILDS_MONTHLY},
    "id": "GuildOne",
    "subscription": BASE_SUBSCRIPTION_EVENT_ID,
    "quantity": 1,
    "current_period_end": EXPIRY_DATE.timestamp(),
}
user_price_id = {
    "price": {"id": STRIPE_PRICE_ID_USERS_MONTHLY},
    "id": "UserOne",
    "subscription": BASE_SUBSCRIPTION_EVENT_ID,
    "quantity": 1,
    "current_period_end": EXPIRY_DATE.timestamp(),
}


class DataT(TypedDict):
    data: list


class SubscriptionT(TypedDict):
    id: str
    items: DataT
    status: Literal[
        "active",
        "incomplete",
        "incomplete_expired",
        "trialing",
        "unpaid",
        "canceled",
        "past_due",
        "paused",
    ]
    customer: str | None


empty_sub: SubscriptionT = {
    "items": {"data": []},
    "status": "active",
    "customer": BASE_CUSTOMER_EMAIL,
    "id": BASE_SUBSCRIPTION_EVENT_ID,
}


class EventObjectT(TypedDict):
    object: SubscriptionT


class EventT(TypedDict):
    data: EventObjectT


# Minimal https://docs.stripe.com/api/events/object
empty_event: EventT = {"data": {"object": empty_sub}}


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
        await payments.handle_customer_subscription_created(empty_event)

    assert caplog.messages == [
        f"Got asked to fulfil guild purchase for '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"but was already handled"
    ]


async def test_with_no_guild_items(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests fulfil_guild_purchase does nothing unless the its price SKU is purchased."""
    Given.user(BASE_CUSTOMER_EMAIL)
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event)

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

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildOne' for user '{user.id} ({user.email})'"
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

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 1
    gt_1 = await GuildTokens().objects().first()
    assert gt_1 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_1.expires_at,
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

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["status"] = "unpaid"
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 1
    gt_1 = await GuildTokens().objects().first()
    assert gt_1 is not None
    assert timing.is_within_next_(
        FROZEN_DATE.datetime,
        gt_1.expires_at,
        timedelta(days=1),
    )


# noinspection DuplicatedCode
async def test_with_guild_item_quantity_two(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    guild_price_id_obj = deepcopy(guild_price_id)
    guild_price_id_obj["quantity"] = 2
    test_subscription["items"]["data"].append(guild_price_id_obj)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event)

    assert caplog.messages == [
        f"Created 2 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == QUANTITY_OF_TWO


# noinspection DuplicatedCode
async def test_with_two_guild_items(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    guild_price_id_two = deepcopy(guild_price_id)
    guild_price_id_two["id"] = "GuildTwo"
    test_subscription["items"]["data"].append(guild_price_id_two)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.no_guild_tokens_exist()

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(empty_event)

    assert caplog.messages == [
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildOne' for user '{user.id} ({user.email})'",
        f"Created 1 GuildTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'GuildTwo' for user '{user.id} ({user.email})'",
    ]
    assert await GuildTokens().count() == QUANTITY_OF_TWO


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_when_subscription_is_modified_be_inactive(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Test that when a subscription is updated to be
    inactive we mark GuildTokens as expired(but not deleted).

    """  # noqa: D205
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.x_guild_tokens_exist(
        GuildTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            user=user,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["status"] = "incomplete"
    subscription["items"]["data"].append(guild_price_id)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)

    gt_1 = await GuildTokens().objects().first()
    assert gt_1 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_1.expires_at,
        timedelta(days=6),
    )

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_updated(event)

    gt_2 = await GuildTokens().objects().first()
    assert gt_2 is not None
    assert timing.is_within_next_(
        FROZEN_DATE.datetime,
        gt_2.expires_at,
        timedelta(days=1),
    )


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_when_subscription_has_no_cared_modifications(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Test that nothing changes when we dont care."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.x_guild_tokens_exist(
        GuildTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            user=user,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["items"]["data"].append(guild_price_id)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)

    gt_1 = await GuildTokens().objects().first()
    assert gt_1 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_1.expires_at,
        timedelta(days=6),
    )

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_updated(event)

    gt_2 = await GuildTokens().objects().first()
    assert gt_2 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_2.expires_at,
        timedelta(days=6),
    )


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_subscription_has_new_higher_quantity(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.x_guild_tokens_exist(
        GuildTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            user=user,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    guild_price = deepcopy(guild_price_id)
    guild_price["quantity"] = 2
    subscription["items"]["data"].append(guild_price)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    gt_1 = await GuildTokens().count()
    assert gt_1 == 1

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_updated(event)

    gt_2 = await GuildTokens().count()
    assert gt_2 == QUANTITY_OF_TWO


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_subscription_has_new_lower_quantity(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.x_guild_tokens_exist(
        GuildTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            user=user,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        ),
        GuildTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            user=user,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        ),
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    guild_price = deepcopy(guild_price_id)
    guild_price["quantity"] = 1
    subscription["items"]["data"].append(guild_price)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    gt_1 = await GuildTokens().count()
    assert gt_1 == QUANTITY_OF_TWO

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_updated(event)

    gt_2 = await GuildTokens().count()
    assert gt_2 == QUANTITY_OF_ONE
