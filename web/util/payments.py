from typing import Final
import datetime
import logging

import arrow
import stripe

from web import constants
from web.tables import GuildTokens, Users
from web.util.table_mixins import utc_now

logger = logging.getLogger(__name__)
PROVISION_STATUS_TYPES: Final = ("active", "trialing")


async def extract_subscription_skus(event) -> list[str]:
    data = []
    for item in event["data"]["object"]["items"]["data"]:
        data.append(item["price"]["id"])  # noqa: PERF401
    return data


async def handle_customer_subscription_created(event) -> None:
    customer_id: str = event["data"]["object"]["customer"]
    customer = await stripe.Customer.retrieve_async(customer_id)
    user = await Users.objects().get(Users.email == customer["email"])
    assert user is not None
    subscription_id: str = event["data"]["object"]["id"]

    # noinspection protected-member
    async with GuildTokens._meta.db.transaction():
        does_exist = await GuildTokens.exists().where(
            GuildTokens.subscription_id == subscription_id
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
                },
            )
            return

        subscription = await stripe.Subscription.retrieve_async(subscription_id)
        for item in subscription["items"]["data"]:
            if item["price"]["id"] != constants.STRIPE_PRICE_ID_GUILDS_MONTHLY:
                # TODO Handle other stripe purchases when implemented
                logger.debug(
                    "Observed price id '%s' not needing to be "
                    "handled by fulfil_guild_purchase",
                    item["price"]["id"],
                    extra={
                        "user.id": user.id,
                        "user.email": user.email,
                        "stripe.subscription.id": subscription_id,
                    },
                )
                continue

            # invoice.paid will also update the expiry to be more correct as required
            if subscription["status"] in PROVISION_STATUS_TYPES:
                sub_expires_at = arrow.get(item["current_period_end"]).shift(days=5)
            else:
                # Create the entry but wait for invoice.paid
                # to actually enable it
                sub_expires_at = arrow.get(utc_now())

            for _ in range(item["quantity"]):
                # Make one token per entry
                guild_token = GuildTokens(
                    subscription_id=subscription_id,
                    user=user,
                    used_for_guild=None,
                    expires_at=sub_expires_at.datetime,
                )
                await guild_token.save()

            logger.debug(
                "Created %s GuildTokens for subscription '%s' and data "
                "'%s' for user '%s (%s)'",
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


async def update_guild_tokens_expiry_from_subscription(
    subscription_id: str, expires_at: datetime.datetime
) -> None:
    for gt in await GuildTokens.objects().where(
        GuildTokens.subscription_id == subscription_id
    ):
        gt.expires_at = expires_at
        await gt.save()


async def handle_customer_subscription_updated(event) -> None:
    """Handle changes to a subscription."""
    # Two key cases are increase or decrease quantity
    subscription = event["data"]["object"]
    for item in subscription["items"]["data"]:
        if item["price"]["id"] != constants.STRIPE_PRICE_ID_GUILDS_MONTHLY:
            # TODO Handle other stripe purchases when implemented
            continue

        subscription_id = item["subscription"]
        stripe_total = item["quantity"]
        current_total = await GuildTokens.count().where(
            GuildTokens.subscription_id == subscription_id
        )

        expires_at = (
            arrow.get(item["current_period_end"]).shift(days=5)
            if subscription["status"] in PROVISION_STATUS_TYPES
            else arrow.get(utc_now())
        )
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
                )
                await guild_token.save()

        elif stripe_total < current_total:
            # we need less
            logger.debug(
                "User decreased guilds on current subscription",
                extra={"stripe.subscription.id": subscription_id},
            )
            all_gc = await GuildTokens.objects().where(
                GuildTokens.subscription_id == subscription_id
            )
            for i in range(current_total - stripe_total):
                try:
                    gc = all_gc[i]
                except IndexError:
                    # sometimes this gets out of sync
                    # if stripe has a number that didnt get built in our db
                    break
                await gc.delete().where(GuildTokens.id == gc.id)


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
            guild_items = [
                i
                for i in subscription["items"]["data"]
                if i["price"]["id"] == constants.STRIPE_PRICE_ID_GUILDS_MONTHLY
            ]
            if len(guild_items) == 0:
                logger.critical("Expected at-least one guild sku, found none")
                continue

            expires_at = (
                arrow.get(guild_items[0]["current_period_end"]).shift(days=5).datetime
            )
            # Try update but if they dont exist then subscription create will set
            # the correct value for us anyway
            all_objects = await GuildTokens.objects().where(
                GuildTokens.subscription_id == subscription_id
            )
            for gc in all_objects:
                gc.expires_at = expires_at
                await gc.save()

            logger.debug(
                "Updated %s GuildTokens within invoice.paid",
                len(all_objects),
                extra={"stripe.subscription.id": subscription_id},
            )
