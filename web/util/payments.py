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


async def fulfil_guild_purchase(subscription_id: str, *, user: Users) -> None:
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

        # Guild is a month so give them this for now and
        # invoice.paid will go update it anyway
        subscription = await stripe.Subscription.retrieve_async(subscription_id)
        expires_at_redis = await constants.REDIS_CLIENT.getdel(
            f"stripe:invoice_paid:{subscription_id}"
        )
        if expires_at_redis is None:
            # Invoice.paid event will handle
            expires_at = utc_now()
        else:
            assert isinstance(expires_at_redis, bytes)
            expires_at = arrow.get(expires_at_redis.decode("utf-8"))

        # expires_at = arrow.get(utc_now()).shift(months=1, days=5).datetime
        for item in subscription["items"]["data"]:
            if item["price"]["id"] != constants.STRIPE_PRICE_ID_GUILDS_MONTHLY:
                # We expect each fulfil to be able to receive a checkout
                # cart that also contains other items which have been purchased
                #
                # equivalant methods should already have been called for say user tokens
                continue

            for _ in range(item["quantity"]):
                # Make one token per entry
                guild_token = GuildTokens(
                    subscription_id=subscription_id,
                    user=user,
                    used_for_guild=None,
                    expires_at=expires_at,
                )
                await guild_token.save()
