import datetime
import logging
from datetime import timedelta
from urllib.parse import quote_plus

import arrow
import orjson
import stripe
from litestar import Controller, get, Request, post
from litestar.response import Template, Redirect
from starlette.datastructures import State
from starlette.responses import Response

from web import constants
from web.controllers import AuthController
from web.middleware import EnsureAuth
from web.tables import Users, GuildTokens
from web.util import html_template, alert
from web.util.table_mixins import utc_now

log = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class StripeController(Controller):
    path = "/stripe"
    include_in_schema = False

    @get("/customer-portal", name="stripe_customer_portal", middleware=[EnsureAuth])
    async def redirect_to_customer_portal(
        self, request: Request[Users, None, State]
    ) -> Redirect:
        return Redirect(
            f"{constants.STRIPE_CUSTOMER_PORTAL}?prefilled_email={quote_plus(request.user.email)}"
        )

    @post("/webhook", name="stripe_webhook", exclude_from_csrf=True)
    async def stripe_webhook(self, request: Request[Users, None, State]) -> Response:
        payload = await request.body()
        sig_header = request.headers["stripe-signature"]
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, constants.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            # Invalid payload
            return Response(status_code=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return Response(status_code=400)

        event_type: str = event["type"]
        # if event_type in (
        #     "checkout.session.completed",
        #     "checkout.session.async_payment_succeeded",
        # ):
        if event_type == "customer.subscription.created":
            # Create new subscriptions
            customer = await stripe.Customer.retrieve_async(
                event["data"]["object"]["customer"]
            )
            user_from_session = await Users.objects().get(
                Users.email == customer["email"]
            )
            await self.fulfil_guild_purchase(
                event["data"]["object"]["id"],
                user=user_from_session,
            )

        elif event_type == "customer.subscription.updated":
            # Two key cases are increase or decrease quantity
            for item in event["data"]["object"]["items"]["data"]:
                if item["price"]["id"] != constants.STRIPE_PRICE_ID_GUILDS:
                    # We expect each fulfil to be able to receive a checkout
                    # cart that also contains other items which have been purchased
                    continue

                subscription_id = item["subscription"]
                stripe_total = item["quantity"]
                current_total = await GuildTokens.count().where(
                    GuildTokens.subscription_id == subscription_id
                )
                if stripe_total == current_total:
                    # Something else changed
                    continue

                elif stripe_total > current_total:
                    # We need more
                    log.debug(
                        "User increased guilds on current subscription",
                        extra={"stripe.subscription.id": subscription_id},
                    )
                    customer = await stripe.Customer.retrieve_async(
                        event["data"]["object"]["customer"]
                    )
                    user_from_session = await Users.objects().get(
                        Users.email == customer["email"]
                    )
                    expires_at = (
                        arrow.get(item["current_period_end"]).shift(days=5).datetime
                    )
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
                    log.debug(
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

        elif event_type == "customer.subscription.deleted":
            skus = await self.extract_subscription_skus(event)
            for sku in skus:
                if sku == constants.STRIPE_PRICE_ID_GUILDS:
                    # Revoke guild premium tokens
                    subscription_id: str = event["data"]["object"]["id"]
                    all_objects = await GuildTokens.objects().where(
                        GuildTokens.subscription_id == subscription_id
                    )
                    for gc in all_objects:
                        await gc.invalidate()

        elif event_type == "invoice.paid":
            for line_item in event["data"]["object"]["lines"]:
                if (
                    line_item["pricing"]["price_details"]["price"]
                    == constants.STRIPE_PRICE_ID_GUILDS
                ):
                    subscription_id = line_item["parent"]["subscription_item_details"][
                        "subscription"
                    ]
                    subscription = await stripe.Subscription.retrieve_async(
                        subscription_id
                    )
                    guild_items = [
                        i
                        for i in subscription["items"]
                        if i["price"]["id"] == constants.STRIPE_PRICE_ID_GUILDS
                    ]
                    if len(guild_items) == 0:
                        log.critical("Expected at-least one guild sku, found none")
                        continue

                    expires_at = (
                        arrow.get(guild_items[0]["current_period_end"])
                        .shift(days=5)
                        .datetime
                    )
                    # For if invoice event comes before subscription create
                    await constants.REDIS_CLIENT.set(
                        f"stripe:invoice_paid:{subscription_id}",
                        expires_at.isoformat(),
                        ex=datetime.timedelta(hours=1),
                    )
                    all_objects = await GuildTokens.objects().where(
                        GuildTokens.subscription_id == subscription_id
                    )
                    for gc in all_objects:
                        gc.expires_at = expires_at
                        await gc.save()

        print(event["type"])

        return Response(status_code=200)

    async def extract_subscription_skus(self, event) -> list[str]:
        data = []
        for item in event["data"]["object"]["items"]["data"]:
            data.append(item["price"]["id"])
        return data

    async def fulfil_guild_purchase(self, subscription_id: str, *, user: Users):
        # redis_key = f"stripe:fulfil_guild_purchase:{subscription_id}"
        # result = await constants.REDIS_CLIENT.set(
        #     redis_key, subscription_id, nx=True, ex=timedelta(hours=2)
        # )
        # if result is None:
        #     # This ID has been handled recently
        #     return

        async with GuildTokens._meta.db.transaction():
            does_exist = await GuildTokens.exists().where(
                GuildTokens.subscription_id == subscription_id
            )
            if does_exist:
                # Already handled way in the past
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
                expires_at = arrow.get(expires_at_redis.decode("utf-8"))

            # expires_at = arrow.get(utc_now()).shift(months=1, days=5).datetime
            for item in subscription["items"]["data"]:
                if item["price"]["id"] != constants.STRIPE_PRICE_ID_GUILDS:
                    # We expect each fulfil to be able to receive a checkout
                    # cart that also contains other items which have been purchased
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

    @get("/guilds/callback", name="stripe_guild_callback", middleware=[EnsureAuth])
    async def guild_callback(
        self, request: Request, checkout_session_id: str
    ) -> Template | Redirect:
        checkout_session = await stripe.checkout.Session.retrieve_async(
            checkout_session_id
        )
        await self.fulfil_guild_purchase(
            checkout_session["subscription"], user=request.user
        )
        alert(
            request,
            "Purchase successful! You may now redeem premium in guilds.",
            level="success",
        )
        if "next_route" in request.cookies:
            next_route = AuthController.validate_next_route(
                next_route=request.cookies["next_route"]
            )
            response: Redirect = Redirect(next_route)
            response.delete_cookie("next_route")
            return response

        return html_template("stripe/thanks.jinja")

    @get("/guilds/checkout", name="stripe_guild_checkout", middleware=[EnsureAuth])
    async def checkout_guild(self) -> Template:
        price_result = await stripe.Price.retrieve_async(constants.STRIPE_PRICE_ID_GUILDS)
        return html_template(
            "stripe/guild_checkout.jinja",
            {"pricing": price_result},
        )

    @post("/guilds/checkout", middleware=[EnsureAuth])
    async def create_guild_checkout(
        self,
        request: Request[Users, None, State],
        allow_promo_code: bool = False,
        next_route: str | None = None,
    ) -> Redirect:
        form = await request.form()
        try:
            quantity = int(form.get("quantity", 1))
        except ValueError:
            quantity = 1

        if quantity <= 0:
            raise ValueError("quantity must be a positive integer.")

        addons = {}
        if allow_promo_code:
            addons["allow_promotion_codes"] = True
        else:
            coupon_result = await stripe.Coupon.retrieve_async(
                constants.STRIPE_COUPON_EARLY_ADOPTER
            )
            addons["discounts"] = [{"coupon": coupon_result["id"]}]

        checkout_session = await stripe.checkout.Session.create_async(
            line_items=[
                {
                    "price": constants.STRIPE_PRICE_ID_GUILDS,
                    "quantity": quantity,
                },
            ],
            customer_email=request.user.email,
            mode="subscription",
            success_url=request.url_for("stripe_guild_callback")
            + "?checkout_session_id={CHECKOUT_SESSION_ID}",
            **addons,
        )
        response: Redirect = Redirect(checkout_session.url, status_code=303)
        if next_route is not None:
            response.set_cookie(
                key="next_route",
                value=next_route,
                httponly=True,
                secure=constants.IS_PRODUCTION,
                max_age=int(timedelta(minutes=30).total_seconds()),
                samesite="lax",
            )
        return response
