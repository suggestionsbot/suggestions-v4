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

from bot.tables import InternalErrors
from shared.utils.ntfy import notify_ethan_of_something
from web import constants
from web.controllers import AuthController
from web.middleware import EnsureAuth, EnsureAdmin
from web.tables import Users, GuildTokens
from web.util import html_template, alert, payments
from web.util.table_mixins import utc_now

log = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class StripeController(Controller):
    path = "/stripe"
    include_in_schema = False
    middleware = [EnsureAdmin]  # TODO Change when live  # noqa: RUF012

    @get("/customer-portal", name="stripe_customer_portal", middleware=[EnsureAuth])
    async def redirect_to_customer_portal(
        self,
        request: Request[Users, None, State],  # ty:ignore[invalid-type-arguments]
    ) -> Redirect:
        return Redirect(
            f"{constants.STRIPE_CUSTOMER_PORTAL}?prefilled_email={quote_plus(request.user.email)}"
        )

    @post("/webhook", name="stripe_webhook", exclude_from_csrf=True)
    async def stripe_webhook(self, request: Request[Users, None, State]) -> Response:  # ty:ignore[invalid-type-arguments]
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
        try:
            if event_type == "customer.subscription.created":
                # New subscription was created that may or may not be paid for
                await payments.handle_customer_subscription_created(event)

            elif event_type == "customer.subscription.updated":
                await payments.handle_customer_subscription_updated(event)

            elif event_type == "customer.subscription.deleted":
                await payments.handle_customer_subscription_deleted(event)

            elif event_type == "invoice.payment_failed":
                await payments.handle_invoice_payment_failed(event)

            elif event_type == "invoice.paid":
                await payments.handle_invoice_paid(event)

        except Exception as e:
            internal_error: InternalErrors = await InternalErrors.persist_error(
                e,
                command_name="Stripe Webhook",
                extra_info=f"{event_type=} event_id={event['id']}",
            )
            await notify_ethan_of_something(
                title="Error in stripe webhook",
                message=f"Observed {e.__class__.__name__} in the stripe webook",
                internal_error_reference=internal_error,
                tags="warning",
            )

        print(event["type"])

        return Response(status_code=200)

    @get("/guilds/callback", name="stripe_guild_callback", middleware=[EnsureAuth])
    async def guild_callback(
        self, request: Request, checkout_session_id: str
    ) -> Template | Redirect:
        checkout_session = await stripe.checkout.Session.retrieve_async(
            checkout_session_id
        )
        await payments.handle_customer_subscription_created(
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
        price_result = await stripe.Price.retrieve_async(
            constants.STRIPE_PRICE_ID_GUILDS_MONTHLY
        )
        return html_template(
            "stripe/guild_checkout.jinja",
            {"pricing": price_result},
        )

    @post("/guilds/checkout", middleware=[EnsureAuth])
    async def create_guild_checkout(
        self,
        request: Request[Users, None, State],  # ty:ignore[invalid-type-arguments]
        allow_promo_code: bool = False,
        next_route: str | None = None,
    ) -> Redirect:
        form = await request.form()
        try:
            quantity = int(form.get("quantity", 1))
        except ValueError:
            quantity = 1

        if quantity <= 0:
            msg = "quantity must be a positive integer."
            raise ValueError(msg)

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
                    "price": constants.STRIPE_PRICE_ID_GUILDS_MONTHLY,
                    "quantity": quantity,
                },
                # TODO Implement yearly support later
                # {
                #     "price": constants.STRIPE_PRICE_ID_GUILDS_YEARLY,
                #     "quantity": quantity,
                # },
            ],
            customer_email=request.user.email,
            mode="subscription",
            success_url=request.url_for("stripe_guild_callback")
            + "?checkout_session_id={CHECKOUT_SESSION_ID}",
            **addons,
        )
        redirect_url = checkout_session.url
        assert isinstance(redirect_url, str)
        response: Redirect = Redirect(redirect_url, status_code=303)
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
