from datetime import timedelta

import arrow
import orjson
from web.constants import REDIS_CLIENT
import secrets

from litestar import Controller, get, Request, post
from litestar.response import Template, Redirect

from web.middleware import EnsureAdmin, EnsureAuth
from web.tables import OAuthEntry, GuildTokens
from web.util import html_template, alert


class GiftController(Controller):
    middleware = [EnsureAuth]
    include_in_schema = False
    path = "/gifts"
    GIFT_EX = timedelta(weeks=8)

    @get(path="/", name="create_gift", middleware=[EnsureAdmin])
    async def create_gift(self, request: Request) -> Template:
        return html_template(
            "gifts/create.jinja",
            context={
                "gift_url": None,
            },
        )

    @post(path="/", middleware=[EnsureAdmin])
    async def create_gift_post(self, request: Request) -> Template:
        form = await request.form()
        amount = int(form.get("quantity", 1))
        user = int(form.get("user_id")) if form.get("user_id", "").isnumeric() else None  # ty:ignore[invalid-argument-type]
        weeks = form.get("weeks") or 4
        weeks = int(weeks)
        code = secrets.token_hex(32) if user is None else secrets.token_hex(16)
        gift_data = {
            "code": code,
            "amount": amount,
            "user_id": user,
            "weeks": weeks,
            "created_by_user_id": request.user.id,
        }
        await REDIS_CLIENT.set(f"gifts:{code}", orjson.dumps(gift_data), ex=self.GIFT_EX)
        gift_url = request.url_for("redeem_gift") + f"?code={code}"
        return html_template(
            "gifts/create.jinja",
            context={
                "gift_url": gift_url,
            },
        )

    @classmethod
    async def validate_code(
        cls, request: Request, code: str
    ) -> tuple[dict | None, Redirect | None]:
        code_entry = await REDIS_CLIENT.get(f"gifts:{code}")
        if not code_entry:
            alert(request, "Unknown Gift.", level="error")
            return None, Redirect("/")

        code_data = orjson.loads(code_entry)
        user_id: int | None = (
            int(code_data["user_id"]) if code_data["user_id"] is not None else None
        )
        if user_id is not None:
            oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
            if oauth_entry.oauth_id != user_id:
                alert(request, "You cannot redeem this gift.", level="warning")
                return None, Redirect("/")

        return code_data, None

    @get(path="/redeem", name="redeem_gift")
    async def redeem_gift(self, request: Request, code: str) -> Template | Redirect:
        code_data, redirect = await self.validate_code(request, code)
        if redirect is not None:
            return redirect
        assert code_data is not None

        return html_template(
            "gifts/redeem.jinja",
            context={
                "amount": code_data["amount"],
                "weeks": code_data["weeks"],
            },
        )

    @post(path="/redeem")
    async def redeem_gift_post(self, request: Request, code: str) -> Redirect | Template:
        code_data, redirect = await self.validate_code(request, code)
        if redirect is not None:
            return redirect
        assert code_data is not None

        creator_id = code_data["created_by_user_id"]
        for i in range(code_data["amount"]):
            gt = GuildTokens(
                subscription_id=f"gift from user with ID {creator_id}",
                subscription_item_id=f"gift {i} of {code_data['amount']}",
                user=request.user,
                expires_at=arrow.get().shift(weeks=code_data["weeks"]).datetime,
            )
            await gt.save()

        alert(request, "Your gift has been redeemed!", level="success")
        return html_template("stripe/thanks.jinja")
