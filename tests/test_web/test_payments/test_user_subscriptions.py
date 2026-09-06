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

from tests.conftest import BaseGiven, BaseWhen, UserTokenT
from web import constants
from web.tables import UserTokens, GuildTokens
from web.util import payments

Given = BaseGiven()

DISCORD_USER_ID = 12349876
QUANTITY_OF_ZERO: Final = 0
QUANTITY_OF_ONE: Final = 1
QUANTITY_OF_TWO: Final = 2
STRIPE_PRICE_ID_GUILDS_MONTHLY = "TestGuildPriceID"
STRIPE_PRICE_ID_USERS_MONTHLY = "TestUserPriceID"
FROZEN_DATE = arrow.get("2012-01-14")
EXPIRY_DATE = arrow.get("2012-02-14")
BASE_CUSTOMER_EMAIL = "tests@suggestions.gg"
BASE_SUBSCRIPTION_EVENT_ID = "SubscriptionEventID"
BASE_SUBSCRIPTION_ITEM_ID = "UserOne"
BASE_INVOICE_EVENT_ID = "InvoiceEventID"
BASE_CUSTOMER_ID = "CustomerId"
guild_price_id = {
    "price": {"id": STRIPE_PRICE_ID_GUILDS_MONTHLY},
    "id": BASE_SUBSCRIPTION_ITEM_ID,
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


class PriceDetailsT(TypedDict):
    price: str  # Price ID
    # product: str  # Associated product


class PricingT(TypedDict):
    price_details: PriceDetailsT


class InvoiceSubT(TypedDict):
    subscription: str | None  # Sub id


class InvoiceParentT(TypedDict):
    subscription_item_details: InvoiceSubT | None


class InvoiceLineEntryT(TypedDict):
    pricing: PricingT
    parent: InvoiceParentT | None


class InvoiceDataT(TypedDict):
    data: list[InvoiceLineEntryT]


class InvoiceT(TypedDict):
    id: str
    lines: InvoiceDataT
    status: Literal["draft", "open", "paid", "uncollectible", "void"]
    customer: str | None


empty_invoice: InvoiceT = {
    "lines": {"data": []},
    "status": "paid",
    "customer": BASE_CUSTOMER_EMAIL,
    "id": BASE_INVOICE_EVENT_ID,
}
guild_invoice_data: InvoiceLineEntryT = {
    "pricing": {"price_details": {"price": STRIPE_PRICE_ID_GUILDS_MONTHLY}},
    "parent": {"subscription_item_details": {"subscription": BASE_SUBSCRIPTION_EVENT_ID}},
}
user_invoice_data: InvoiceLineEntryT = {
    "pricing": {"price_details": {"price": STRIPE_PRICE_ID_USERS_MONTHLY}},
    "parent": {"subscription_item_details": {"subscription": BASE_SUBSCRIPTION_EVENT_ID}},
}


class EventObjectT(TypedDict):
    object: SubscriptionT | InvoiceT


class EventT(TypedDict):
    data: EventObjectT


# Minimal https://docs.stripe.com/api/events/object
empty_event: EventT = {"data": {"object": empty_sub}}


# Minimal https://docs.stripe.com/api/customers/object
class CustomerT(TypedDict):
    email: str
    id: str
    name: str


base_customer: CustomerT = {
    "email": BASE_CUSTOMER_EMAIL,
    "id": BASE_CUSTOMER_ID,
    "name": "TestName",
}


class PaymentWhen(BaseWhen):
    @staticmethod
    def stripe_subscription_is_patched_with_(
        monkeypatch: pytest.MonkeyPatch, sub_object: SubscriptionT
    ) -> None:
        mock = AsyncMock()
        mock.return_value = sub_object
        monkeypatch.setattr(stripe.Subscription, "retrieve_async", mock)
        PaymentWhen.patch_sku_constants(monkeypatch)

    @staticmethod
    def patch_sku_constants(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            constants, "STRIPE_PRICE_ID_GUILDS_MONTHLY", STRIPE_PRICE_ID_GUILDS_MONTHLY
        )
        monkeypatch.setattr(
            constants, "STRIPE_PRICE_ID_USERS_MONTHLY", STRIPE_PRICE_ID_USERS_MONTHLY
        )

    @staticmethod
    def stripe_customer_is_patched_with_(
        monkeypatch: pytest.MonkeyPatch, customer: CustomerT
    ) -> None:
        mock = AsyncMock()
        mock.return_value = customer
        monkeypatch.setattr(stripe.Customer, "retrieve_async", mock)


When = PaymentWhen()


async def test_user_existing_subscription(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests the handling of duplicate subscription calls."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.user_tokens_exist(
        UserTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            subscription_item_id=BASE_SUBSCRIPTION_ITEM_ID,
            user=user,
            user_id=DISCORD_USER_ID,
        )
    )
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            customer_id=BASE_CUSTOMER_ID,
        )

    assert [
        f"Got asked to fulfil user purchase for '{BASE_SUBSCRIPTION_EVENT_ID}'"
        f" but was already handled"
    ] == caplog.messages


async def test_with_no_user_items(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests fulfil_guild_purchase does nothing unless the its price SKU is purchased."""
    Given.user(BASE_CUSTOMER_EMAIL)
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            customer_id=BASE_CUSTOMER_ID,
        )

    assert await UserTokens.count() == 0


# noinspection DuplicatedCode
async def test_user_flow_with_no_user_items(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests that it doesn't create UserTokens when none are present."""
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(guild_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            customer_id=BASE_CUSTOMER_ID,
        )

    assert await UserTokens().count() == QUANTITY_OF_ZERO


# noinspection DuplicatedCode
async def test_user_payment_sets_expiry_date(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests it sets expiry to future if paid."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            customer_id=BASE_CUSTOMER_ID,
        )

    assert caplog.messages == [
        f"Created 1 UserTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'UserOne' for user '{user.id} ({user.email})'"
    ]
    assert await GuildTokens().count() == 0
    assert await UserTokens().count() == 1
    ut = await UserTokens().objects().first()
    assert ut is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        ut.expires_at,
        timedelta(days=6),
    )


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_user_payment_sets_expiry_date_when_not_paid(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Tests it sets expiry to now if sub is not active."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object

    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["status"] = "unpaid"
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_created(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            customer_id=BASE_CUSTOMER_ID,
        )

    assert caplog.messages == [
        f"Created 1 UserTokens for subscription '{BASE_SUBSCRIPTION_EVENT_ID}' "
        f"and data 'UserOne' for user '{user.id} ({user.email})'"
    ]
    assert await UserTokens().count() == 1
    ut = await UserTokens().objects().first()
    assert ut is not None
    assert timing.is_within_next_(
        FROZEN_DATE.datetime,
        ut.expires_at,
        timedelta(days=1),
    )


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_when_user_subscription_is_modified_be_inactive(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Test that when a subscription is updated to be
    inactive we mark UserTokens as expired(but not deleted).

    """  # noqa: D205
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.user_tokens_exist(
        UserTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            subscription_item_id=BASE_SUBSCRIPTION_ITEM_ID,
            user=user,
            user_id=DISCORD_USER_ID,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["status"] = "incomplete"
    subscription["items"]["data"].append(user_price_id)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)

    gt_1 = await UserTokens().objects().first()
    assert gt_1 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_1.expires_at,
        timedelta(days=6),
    )

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_updated(event)

    gt_2 = await UserTokens().objects().first()
    assert gt_2 is not None
    assert timing.is_within_next_(
        FROZEN_DATE.datetime,
        gt_2.expires_at,
        timedelta(days=1),
    )


# noinspection DuplicatedCode
@freeze_time(FROZEN_DATE.datetime)
async def test_when_user_subscription_has_no_cared_modifications(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    """Test that nothing changes when we dont care."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.user_tokens_exist(
        UserTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            subscription_item_id=BASE_SUBSCRIPTION_ITEM_ID,
            user=user,
            user_id=DISCORD_USER_ID,
            expires_at=EXPIRY_DATE.shift(days=5).datetime,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["items"]["data"].append(user_price_id)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)

    gt_1 = await UserTokens().objects().first()
    assert gt_1 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_1.expires_at,
        timedelta(days=6),
    )

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_updated(event)

    gt_2 = await UserTokens().objects().first()
    assert gt_2 is not None
    assert timing.is_within_next_(
        EXPIRY_DATE.datetime,
        gt_2.expires_at,
        timedelta(days=6),
    )


# noinspection DuplicatedCode
async def test_user_subscription_deleted_with_associated_guild_tokens(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.user_tokens_exist(
        UserTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            subscription_item_id=BASE_SUBSCRIPTION_ITEM_ID,
            user=user,
            user_id=DISCORD_USER_ID,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["items"]["data"].append(guild_price_id)
    subscription["items"]["data"].append(user_price_id)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)

    gt_1 = await UserTokens().count()
    assert gt_1 == QUANTITY_OF_ONE

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_deleted(event)

    gt_2 = await UserTokens().count()
    assert gt_2 == QUANTITY_OF_ZERO


# noinspection DuplicatedCode
async def test_user_invoice_payment_failed_with_associated_guild_tokens(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.user_tokens_exist(
        UserTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            subscription_item_id=BASE_SUBSCRIPTION_ITEM_ID,
            user=user,
            user_id=DISCORD_USER_ID,
        )
    )
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["items"]["data"].append(guild_price_id)
    subscription["items"]["data"].append(user_price_id)
    event["data"]["object"] = subscription
    When.stripe_subscription_is_patched_with_(monkeypatch, subscription)

    gt_1 = await UserTokens().count()
    assert gt_1 == QUANTITY_OF_ONE

    with caplog.at_level(logging.DEBUG):
        await payments.handle_invoice_payment_failed(event)

    gt_2 = await UserTokens().count()
    assert gt_2 == QUANTITY_OF_ZERO


async def test_user_subscription_deleted_with_no_associated_guild_tokens(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redis_client: aioredis.Redis,
) -> None:
    event: EventT = deepcopy(empty_event)
    subscription: SubscriptionT = deepcopy(empty_sub)
    subscription["items"]["data"].append(guild_price_id)
    subscription["items"]["data"].append(user_price_id)
    event["data"]["object"] = subscription

    gt_1 = await UserTokens().count()
    assert gt_1 == QUANTITY_OF_ZERO

    with caplog.at_level(logging.DEBUG):
        await payments.handle_customer_subscription_deleted(event)

    gt_2 = await UserTokens().count()
    assert gt_2 == QUANTITY_OF_ZERO


async def test_user_invoice_paid_when_not_paid(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    Given.user(BASE_CUSTOMER_EMAIL)
    test_invoice: InvoiceT = deepcopy(empty_invoice)
    test_invoice["status"] = "open"
    event: EventT = deepcopy(empty_event)
    event["data"]["object"] = test_invoice
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_invoice_paid(event)

    assert caplog.messages == ["Invoice not marked as paid asked to handle pay method"]


async def test_user_invoice_paid_with_no_user_items(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that it does nothing unless the user price SKU is purchased."""
    Given.user(BASE_CUSTOMER_EMAIL)
    test_invoice: InvoiceT = deepcopy(empty_invoice)
    test_invoice["lines"]["data"].append(user_invoice_data)
    event: EventT = deepcopy(empty_event)
    event["data"]["object"] = test_invoice
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.patch_sku_constants(monkeypatch)
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_invoice_paid(event)

    assert caplog.messages == ["Updated 0 UserTokens within invoice.paid"]


@freeze_time(FROZEN_DATE.datetime)
async def test_user_invoice_paid_with_user_items(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that it does nothing unless the user price SKU is purchased."""
    user = Given.user(BASE_CUSTOMER_EMAIL).object
    Given.user_tokens_exist(
        UserTokenT(
            subscription_id=BASE_SUBSCRIPTION_EVENT_ID,
            subscription_item_id=BASE_SUBSCRIPTION_ITEM_ID,
            user=user,
            user_id=DISCORD_USER_ID,
        )
    )
    test_invoice: InvoiceT = deepcopy(empty_invoice)
    test_invoice["lines"]["data"].append(user_invoice_data)
    event: EventT = deepcopy(empty_event)
    event["data"]["object"] = test_invoice
    When.stripe_customer_is_patched_with_(monkeypatch, base_customer)
    When.patch_sku_constants(monkeypatch)
    test_subscription: SubscriptionT = deepcopy(empty_sub)
    test_subscription["items"]["data"].append(user_price_id)
    When.stripe_subscription_is_patched_with_(monkeypatch, test_subscription)

    with caplog.at_level(logging.DEBUG):
        await payments.handle_invoice_paid(event)

    assert caplog.messages == ["Updated 1 UserTokens within invoice.paid"]
    gc_1 = await UserTokens.objects().first()
    assert gc_1 is not None
    assert timing.is_within_next_(
        gc_1.expires_at,
        EXPIRY_DATE.shift(days=5).datetime,
        timedelta(days=7),
    )
