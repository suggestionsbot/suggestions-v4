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
from web.controllers.oauth_controller import DISCORD_OAUTH
from web.middleware import EnsureAuth, EnsureAdmin
from web.tables import Users, GuildTokens, OAuthEntry
from web.util import html_template, alert, payments
from web.util.table_mixins import utc_now

log = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class StripeController(Controller):
    path = "/stripe"
    include_in_schema = False
    # middleware = [EnsureAdmin]  # TODO Change when live  # noqa: RUF012

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
            log.debug("Observed %s", event["type"])
            if event_type == "customer.subscription.created":
                # New subscription was created that may or may not be paid for
                customer_id: str = event["data"]["object"]["customer"]
                subscription_id: str = event["data"]["object"]["id"]
                await payments.handle_customer_subscription_created(
                    subscription_id=subscription_id, customer_id=customer_id
                )

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
            return Response(status_code=500)

        return Response(status_code=200)

    @get("/guilds/callback", name="stripe_guild_callback", middleware=[EnsureAuth])
    async def guild_callback(
        self, request: Request, checkout_session_id: str
    ) -> Template | Redirect:
        checkout_session = await stripe.checkout.Session.retrieve_async(
            checkout_session_id
        )
        subscription = await stripe.Subscription.retrieve_async(
            checkout_session["subscription"]
        )
        await payments.handle_customer_subscription_created(
            subscription_id=checkout_session["subscription"],
            customer_id=subscription["customer"],
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
            msg = "Quantity must be a positive number."
            alert(request, msg, level="error")
            return Redirect(request.url_for("stripe_guild_checkout"))

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

    @get("/guilds/tokens", name="manage_guild_tokens", middleware=[EnsureAuth])
    async def manage_guild_tokens(self, request: Request) -> Template:
        guild_tokens = (
            await GuildTokens.objects()
            .where(GuildTokens.user == request.user)
            .order_by(GuildTokens.id)
        )
        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        guilds = await DISCORD_OAUTH.get_user_guilds(
            oauth_entry.access_token, user_id=oauth_entry.oauth_id
        )
        guild_names = {int(i["id"]): i["name"] for i in guilds}
        return html_template(
            "stripe/guild_tokens.jinja",
            {
                "tokens": guild_tokens,
                "guilds": guilds,
                "guild_names": guild_names,
            },
        )

    @post("/guilds/tokens", middleware=[EnsureAuth])
    async def manage_guild_tokens_post(self, request: Request) -> Redirect:
        form = await request.form()
        row: str | None = form.get("row", None)
        redirect_url = Redirect(request.url_for("manage_guild_tokens"))
        if row is None or (row is not None and not row.isdigit()):
            alert(
                request,
                "Missing row information, please reload the page and try again.",
                level="error",
            )
            return redirect_url

        guild_token = (
            await GuildTokens.objects()
            .where(GuildTokens.user == request.user)
            .where(GuildTokens.id == int(row))
            .first()
        )
        if guild_token is None:
            alert(
                request,
                "Missing row, please reload the page and try again.",
                level="error",
            )
            return redirect_url

        radio_result = form.get("radios", None)
        if radio_result is not None and not radio_result.isdigit():
            alert(
                request,
                "Missing guild information, please reload the page and try again.",
                level="error",
            )
            return redirect_url

        if radio_result is None:
            guild_token.used_for_guild = None
            alert(
                request,
                "I have removed that guilds premium.",
                level="success",
            )

        elif int(radio_result) == guild_token.used_for_guild:
            alert(
                request,
                "You have already assigned premium for that guild.",
                level="info",
            )

        else:
            already_used = (
                await GuildTokens.exists()
                .where(GuildTokens.used_for_guild == int(radio_result))
                .where(utc_now() < GuildTokens.expires_at)
            )
            if already_used:
                alert(
                    request,
                    "That guild already has premium so I didn't let you also provide it.",
                    level="warning",
                )
                return redirect_url

            guild_token.used_for_guild = int(radio_result)
            alert(
                request,
                "I have added premium for that guild.",
                level="success",
            )
        await guild_token.save()
        return redirect_url
