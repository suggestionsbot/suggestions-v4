import logging

import arrow
import stripe

from web import constants
from web.tables import GuildTokens, Users
from web.util.table_mixins import utc_now

logger = logging.getLogger(__name__)


async def extract_subscription_skus(event) -> list[str]:
    data = []
    for item in event["data"]["object"]["items"]["data"]:
        data.append(item["price"]["id"])
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
                # We expect each fulfil to be able to receive a checkout
                # cart that also contains other items which have been purchased
                #
                # equivalant methods should already have been called for say user tokens
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
            if subscription["status"] in ("active", "trialing"):
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
