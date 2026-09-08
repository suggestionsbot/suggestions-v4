import secrets
from typing import Final
import datetime
import logging

import arrow
import stripe
from arrow import Arrow

from shared.utils.ntfy import notify_ethan_of_something
from web import constants
from web.tables import GuildTokens, Users, UserTokens
from web.util.table_mixins import utc_now

logger = logging.getLogger(__name__)
PROVISION_STATUS_TYPES: Final = ("active", "trialing")


async def extract_subscription_skus(event) -> list[str]:
    data = []
    for item in event["data"]["object"]["items"]["data"]:
        data.append(item["price"]["id"])  # noqa: PERF401
    return data


async def provision_new_guild_subscription(
    item, *, subscription_id: str, user: Users, subscription_status: str
) -> None:
    subscription_item_id = item["id"]
    does_exist = (
        await GuildTokens.exists()
        .where(GuildTokens.subscription_id == subscription_id)
        .where(GuildTokens.subscription_item_id == subscription_item_id)
    )
    if does_exist:
        # Already handled way in the past
        logger.debug(
            "Got asked to fulfil guild purchase for '%s' but was already handled",
            subscription_id,
            extra={
                "user.id": user.id,
                "user.email": user.email,
                "stripe.subscription.id": subscription_id,
                "stripe.subscription.item.id": subscription_item_id,
            },
        )
        return

    sub_expires_at = await get_subscription_expiry(item, subscription_status)
    for _ in range(item["quantity"]):
        # Make one token per entry
        guild_token = GuildTokens(
            subscription_id=subscription_id,
            user=user,
            used_for_guild=None,
            expires_at=sub_expires_at.datetime,
            subscription_item_id=subscription_item_id,
        )
        await guild_token.save()

    logger.debug(
        "Created %s GuildTokens for subscription '%s' and data '%s' for user '%s (%s)'",
        item["quantity"],
        subscription_id,
        item["id"],
        user.id,
        user.email,
        extra={
            "user.id": user.id,
            "user.email": user.email,
            "stripe.subscription.id": subscription_id,
        },
    )


async def provision_new_user_subscription(
    item, *, subscription_id: str, user: Users, subscription_status: str
) -> None:
    subscription_item_id = item["id"]
    does_exist = (
        await UserTokens.exists()
        .where(UserTokens.subscription_id == subscription_id)
        .where(UserTokens.subscription_item_id == subscription_item_id)
    )
    if does_exist:
        # Already handled way in the past
        logger.debug(
            "Got asked to fulfil user purchase for '%s' but was already handled",
            subscription_id,
            extra={
                "user.id": user.id,
                "user.email": user.email,
                "stripe.subscription.id": subscription_id,
                "stripe.subscription.item.id": subscription_item_id,
            },
        )
        return

    oauth_user = await user.get_oauth_entry()
    assert oauth_user is not None
    sub_expires_at = await get_subscription_expiry(item, subscription_status)
    for _ in range(item["quantity"]):
        # Make one token per entry
        user_token = UserTokens(
            subscription_id=subscription_id,
            user=user,
            user_id=oauth_user.oauth_id,
            expires_at=sub_expires_at.datetime,
            subscription_item_id=subscription_item_id,
        )
        await user_token.save()

    if item["quantity"] != 1:
        message = (
            f"Created more then one UserToken for subscription"
            f" {subscription_id} for user {user.id} ({user.email})"
        )
        logger.warning(message)
        await notify_ethan_of_something(
            title="Extra User Sub",
            message=message + ". Consider going and refunding one.",
        )

    logger.debug(
        "Created %s UserTokens for subscription '%s' and data '%s' for user '%s (%s)'",
        item["quantity"],
        subscription_id,
        item["id"],
        user.id,
        user.email,
        extra={
            "user.id": user.id,
            "user.email": user.email,
            "stripe.subscription.id": subscription_id,
        },
    )


async def get_subscription_expiry(item, subscription_status: str) -> Arrow:
    # invoice.paid will also update the expiry to be more correct as required
    if subscription_status in PROVISION_STATUS_TYPES:
        sub_expires_at = arrow.get(item["current_period_end"]).shift(days=5)
    else:
        # Create the entry but wait for invoice.paid
        # to actually enable it
        sub_expires_at = arrow.get(utc_now())

    return sub_expires_at


async def handle_customer_subscription_created(
    *, subscription_id: str, customer_id: str
) -> None:
    customer = await stripe.Customer.retrieve_async(customer_id)
    user = await Users.objects().get(Users.email == customer["email"])
    if user is None:
        user = Users(
            username=customer["email"],
            name=customer["name"],
            email=customer["email"],
            password=secrets.token_hex(64),
            active=True,
            auths_without_password=True,
        )
        await user.save()

    if user.stripe_customer_id is None:
        user.stripe_customer_id = customer_id
        await user.save()

    # noinspection protected-member
    async with GuildTokens._meta.db.transaction():
        subscription = await stripe.Subscription.retrieve_async(subscription_id)
        for item in subscription["items"]["data"]:
            if item["price"]["id"] == constants.STRIPE_PRICE_ID_GUILDS_MONTHLY:
                await provision_new_guild_subscription(
                    item,
                    subscription_id=subscription_id,
                    user=user,
                    subscription_status=subscription["status"],
                )

            elif item["price"]["id"] == constants.STRIPE_PRICE_ID_USERS_MONTHLY:
                await provision_new_user_subscription(
                    item,
                    subscription_id=subscription_id,
                    user=user,
                    subscription_status=subscription["status"],
                )

            else:
                logger.warning(
                    "Observed price id '%s' needing to be "
                    "handled by handle_customer_subscription_created",
                    item["price"]["id"],
                    extra={
                        "user.id": user.id,
                        "user.email": user.email,
                        "stripe.subscription.id": subscription_id,
                    },
                )
                await notify_ethan_of_something(
                    title="Unknown Stripe Price",
                    message="Observed a price ID not currently handled which should be",
                    tags="warning",
                )


async def update_guild_tokens_expiry_from_subscription(
    subscription_id: str, expires_at: datetime.datetime
) -> None:
    for gt in await GuildTokens.objects().where(
        GuildTokens.subscription_id == subscription_id
    ):
        gt.expires_at = expires_at
        await gt.save()


async def update_user_tokens_expiry_from_subscription(
    subscription_id: str, expires_at: datetime.datetime
) -> None:
    for ut in await UserTokens.objects().where(
        UserTokens.subscription_id == subscription_id
    ):
        ut.expires_at = expires_at
        await ut.save()


async def handle_updated_guild_subscriptions(event) -> None:
    """Handles the update of guild subscriptions."""
    # Two key cases are increase or decrease quantity
    seen_item_ids: set[str] = set()
    subscription = event["data"]["object"]
    subscription_id = subscription["id"]
    for item in subscription["items"]["data"]:
        if item["price"]["id"] != constants.STRIPE_PRICE_ID_GUILDS_MONTHLY:
            continue

        subscription_item_id = item["id"]
        seen_item_ids.add(subscription_item_id)
        stripe_total = item["quantity"]
        current_total = (
            await GuildTokens.count()
            .where(GuildTokens.subscription_id == subscription_id)
            .where(GuildTokens.subscription_item_id == subscription_item_id)
        )

        expires_at = await get_subscription_expiry(item, subscription["status"])
        await update_guild_tokens_expiry_from_subscription(
            subscription_id, expires_at.datetime
        )

        if stripe_total == current_total:
            # Something else changed
            continue

        if stripe_total > current_total:
            # We need more
            logger.debug(
                "User increased guilds on current subscription",
                extra={"stripe.subscription.id": subscription_id},
            )
            customer = await stripe.Customer.retrieve_async(
                event["data"]["object"]["customer"]
            )
            user_from_session = await Users.objects().get(
                Users.email == customer["email"]
            )
            expires_at = arrow.get(item["current_period_end"]).shift(days=5).datetime
            for _ in range(stripe_total - current_total):
                guild_token = GuildTokens(
                    subscription_id=subscription_id,
                    user=user_from_session,
                    used_for_guild=None,
                    expires_at=expires_at,
                    subscription_item_id=subscription_item_id,
                )
                await guild_token.save()

        elif stripe_total < current_total:
            # we need less
            logger.debug(
                "User decreased guilds on current subscription",
                extra={"stripe.subscription.id": subscription_id},
            )
            all_gc = (
                await GuildTokens.objects()
                .where(GuildTokens.subscription_id == subscription_id)
                .where(GuildTokens.subscription_item_id == subscription_item_id)
            )
            for i in range(current_total - stripe_total):
                try:
                    gc = all_gc[i]
                except IndexError:
                    # sometimes this gets out of sync
                    # if stripe has a number that didnt get built in our db
                    break
                await gc.delete().where(GuildTokens.id == gc.id)

    all_item_ids = await GuildTokens.select(GuildTokens.subscription_item_id).where(
        GuildTokens.subscription_id == subscription_id
    )
    all_item_ids_set = {i["subscription_item_id"] for i in all_item_ids}
    removed_items = all_item_ids_set.difference(seen_item_ids)
    if removed_items:
        # Something got removed and rather then do the reasonable thing
        # and look at stripe objects we can just do this
        for removed_item_id in removed_items:
            await (
                GuildTokens.delete()
                .where(GuildTokens.subscription_id == subscription_id)
                .where(GuildTokens.subscription_item_id == removed_item_id)
            )


async def handle_updated_user_subscriptions(event) -> None:
    """Handles the update of user subscriptions.

    We only care about users having one user sub at a time
    so I have decided to ignore quantity here.

    As a result we only update expiry dates
    """
    subscription = event["data"]["object"]
    subscription_id = subscription["id"]
    for item in subscription["items"]["data"]:
        if item["price"]["id"] != constants.STRIPE_PRICE_ID_USERS_MONTHLY:
            continue

        expires_at = await get_subscription_expiry(item, subscription["status"])
        await update_user_tokens_expiry_from_subscription(
            subscription_id, expires_at.datetime
        )


async def handle_customer_subscription_updated(event) -> None:
    """Handle changes to a subscription."""
    await handle_updated_guild_subscriptions(event)
    await handle_updated_user_subscriptions(event)


async def handle_customer_subscription_deleted(event) -> None:
    """Handle the deletion of a subscription as it has ended."""
    skus = await extract_subscription_skus(event)
    for sku in skus:
        if sku == constants.STRIPE_PRICE_ID_GUILDS_MONTHLY:
            # Revoke guild premium tokens
            subscription_id: str = event["data"]["object"]["id"]
            await GuildTokens.delete().where(
                GuildTokens.subscription_id == subscription_id
            )
        elif sku == constants.STRIPE_PRICE_ID_USERS_MONTHLY:
            # Revoke user premium tokens
            subscription_id: str = event["data"]["object"]["id"]
            await UserTokens.delete().where(UserTokens.subscription_id == subscription_id)

        else:
            logger.debug("Unknown subscription sku: %s", sku)


async def handle_invoice_payment_failed(event) -> None:
    """Handle payment failures.

    I don't think we need to do more than this at this point?
    Maybe in future we can notify the user but I think stripe does this.
    """
    await handle_customer_subscription_deleted(event)


async def handle_invoice_paid(event) -> None:
    """Handle paid invoices."""
    if event["data"]["object"]["status"] != "paid":
        # I think this is unreachable?
        logger.critical("Invoice not marked as paid asked to handle pay method")
        return

    for line_item in event["data"]["object"]["lines"]["data"]:
        if (
            line_item["pricing"]["price_details"]["price"]
            == constants.STRIPE_PRICE_ID_GUILDS_MONTHLY
        ):
            subscription_id = line_item["parent"]["subscription_item_details"][
                "subscription"
            ]
            subscription = await stripe.Subscription.retrieve_async(subscription_id)
            user_items = [
                i
                for i in subscription["items"]["data"]
                if i["price"]["id"] == constants.STRIPE_PRICE_ID_GUILDS_MONTHLY
            ]
            if len(user_items) == 0:
                logger.critical("Expected at-least one guild sku, found none")
                continue

            expires_at = (
                arrow.get(user_items[0]["current_period_end"]).shift(days=5).datetime
            )
            # Try update but if they dont exist then subscription create will set
            # the correct value for us anyway
            all_objects = await GuildTokens.objects().where(
                GuildTokens.subscription_id == subscription_id
            )
            for uc in all_objects:
                uc.expires_at = expires_at
                await uc.save()

            logger.debug(
                "Updated %s GuildTokens within invoice.paid",
                len(all_objects),
                extra={"stripe.subscription.id": subscription_id},
            )

        elif (
            line_item["pricing"]["price_details"]["price"]
            == constants.STRIPE_PRICE_ID_USERS_MONTHLY
        ):
            subscription_id = line_item["parent"]["subscription_item_details"][
                "subscription"
            ]
            subscription = await stripe.Subscription.retrieve_async(subscription_id)
            user_items = [
                i
                for i in subscription["items"]["data"]
                if i["price"]["id"] == constants.STRIPE_PRICE_ID_USERS_MONTHLY
            ]
            if len(user_items) == 0:
                logger.critical("Expected at-least one user sku, found none")
                continue

            expires_at = (
                arrow.get(user_items[0]["current_period_end"]).shift(days=5).datetime
            )
            # Try update but if they dont exist then subscription create will set
            # the correct value for us anyway
            all_objects = await UserTokens.objects().where(
                UserTokens.subscription_id == subscription_id
            )
            for uc in all_objects:
                uc.expires_at = expires_at
                await uc.save()

            logger.debug(
                "Updated %s UserTokens within invoice.paid",
                len(all_objects),
                extra={"stripe.subscription.id": subscription_id},
            )
