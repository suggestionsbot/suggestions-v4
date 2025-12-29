import hmac
import logging
import secrets
import typing
import warnings
from datetime import datetime, timedelta

import commons
import httpx
from commons.hibp import has_password_been_pwned
from litestar import Controller, Request, get, post
from litestar.exceptions import SerializationException
from litestar.response import Redirect, Template
from litestar.status_codes import HTTP_303_SEE_OTHER
from piccolo_api.mfa.authenticator.tables import AuthenticatorSecret
from piccolo_api.session_auth.tables import SessionsBase
from tenacity import retry, stop_after_attempt, wait_random, retry_if_not_exception_type

from web import constants
from web.middleware import EnsureAuth
from web.tables import MagicLinks, Users, AuthenticationAttempts, OAuthEntry
from web.util import alert, html_template
from web.util.email import send_email
from web.util.table_mixins import utc_now

log = logging.getLogger(__name__)


class AuthController(Controller):
    path = "/auth"
    auth_table = Users
    mfa_table = AuthenticatorSecret
    session_table = SessionsBase
    session_expiry = timedelta(hours=6)
    max_session_expiry = timedelta(days=3)
    default_redirect_to = "/"
    cookie_name = "id"
    tags = ["Authentication"]
    include_in_schema = False
    account_lockout_period = timedelta(minutes=10)
    account_lockout_limit = 5

    async def do_turnstile_checks(self, request: Request) -> Template | None:
        body = await request.form()
        token = body.get("turnstile-token", None)
        if not token:
            alert(
                request,
                "This route requires you to pass a Cloudflare challenge first. Please give it a go and try again.",
                level="error",
            )
            return self._render_template(
                request,
                "auth/sign_in.jinja",
                status_code=400,
            )

        is_valid_turnstile = await self.validate_cf_turnstile_token(request, token)
        if not is_valid_turnstile:
            alert(
                request,
                "This route requires you to pass a Cloudflare challenge first. Please give it a go and try again.",
                level="error",
            )
            return self._render_template(
                request,
                "auth/sign_in.jinja",
                status_code=400,
            )

        # This means it passed
        return None

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random(min=1, max=2),
        retry=retry_if_not_exception_type(ValueError)
        | retry_if_not_exception_type(AssertionError),
        reraise=True,
    )
    async def validate_cf_turnstile_token(request: Request, token: str) -> bool:
        """Returns True if the token is valid"""
        data = {
            "secret": constants.CF_TURNSTILE_SECRET_KEY,
            "response": token,
        }
        user_ip = request.client.host if request.client else None
        if user_ip is not None:
            data["remoteip"] = user_ip

        try:
            async with httpx.AsyncClient() as client:
                resp: httpx.Response = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    json=data,
                )
                resp.raise_for_status()
                data = resp.json()
                if (
                    data["hostname"] not in constants.SERVING_DOMAIN
                    and constants.IS_PRODUCTION
                ):
                    log.warning(
                        "Someone found a way to get CF tokens from %s on ip %s",
                        data["hostname"],
                        user_ip,
                    )
                    return False

                log.debug(
                    "Cloudflare Turnstile response for IP %s",
                    user_ip,
                    extra={"CF_data": data},
                )
                return data["success"]
        except (httpx.HTTPError, KeyError) as e:
            log.error(
                "Cloudflare Turnstile broke",
                extra={"traceback": commons.exception_as_string(e)},
            )
            return False

    @classmethod
    def validate_next_route(cls, next_route: str) -> str:
        # Basic open redirect checks
        if not next_route.startswith("/"):
            next_route = "/"

        return next_route

    @staticmethod
    def _render_template(
        request: Request, template: str, context: dict = None, *, status_code: int = 200
    ) -> Template:
        csrftoken = request.scope.get("csrftoken")  # type: ignore
        csrf_cookie_name = request.scope.get("csrf_cookie_name")  # type: ignore

        if context is None:
            context = {}

        if constants.USE_CF_TURNSTILE:
            context["CF_TURNSTILE_SITE_KEY"] = constants.CF_TURNSTILE_SITE_KEY

        return html_template(
            template,
            {
                "csrftoken": csrftoken,
                "csrf_cookie_name": csrf_cookie_name,
                "request": request,
                "has_registration": constants.ALLOW_REGISTRATION,
                **context,
            },
            status_code=status_code,
        )

    @classmethod
    async def get_user_for_creds(
        cls, request: Request, username: str, password: str
    ) -> tuple[Users | None, Redirect | Template | None]:
        """Standard auth flow related to a password

        Returns
        -------
        tuple[Users | None, Redirect | Template | None]
            The user if auth is correct else a redirect/template to expected page
        """
        if (not username) or (not password):
            alert(request, "Missing username or password", level="error")
            return None, cls._render_template(
                request, "auth/sign_in.jinja", status_code=400
            )

        user_id = await cls.auth_table.login(
            username=username,
            password=password,
        )

        if not user_id:
            alert(
                request,
                "The username, password or mfa is incorrect.",
                level="error",
            )
            return None, cls._render_template(
                request, "auth/sign_in.jinja", status_code=401
            )

        user_is_active = await Users.exists().where(
            (Users.id == user_id) & (Users.active.eq(True))
        )
        if not user_is_active:
            alert(request, "User is currently disabled.", level="error")
            return None, cls._render_template(
                request, "auth/sign_in.jinja", status_code=403
            )

        return (
            await cls.auth_table.objects().get(cls.auth_table.id == user_id),
            None,
        )

    @staticmethod
    async def details_from_body(request: Request):
        # Some middleware (for example CSRF) has already awaited the request
        # body, and adds it to the request.
        body: typing.Any = request.scope.get("form")  # type: ignore

        if not body:
            try:
                body = await request.json()
            except SerializationException:
                body = await request.form()

        if body is None:
            return None, None, None

        username = body.get("username", None)
        password = body.get("password", None)
        mfa = body.get("mfa", None)
        return username, password, mfa

    @classmethod
    async def create_session_for_user(cls, user: Users) -> str:
        if not constants.IS_PRODUCTION:
            message = (
                "If running sessions in production, make sure 'production' "
                "is set to True, and serve under HTTPS."
            )
            warnings.warn(message)

        now = datetime.now()
        expiry_date = now + cls.session_expiry
        max_expiry_date = now + cls.max_session_expiry

        session: SessionsBase = await cls.session_table.create_session(
            user_id=user.id,  # type: ignore
            expiry_date=expiry_date,
            max_expiry_date=max_expiry_date,
        )

        return typing.cast(str, session.token)

    async def confirm_mfa_was_correct(
        self, request: Request, user: Users, mfa_code: str
    ) -> Redirect | bool | None:
        """Returns None if MFA was valid, Redirect if it needs configuring and False if incorrect"""
        user_is_enrolled = await constants.MFA_TOTP_PROVIDER.is_user_enrolled(user)
        if constants.REQUIRE_MFA or user_is_enrolled:
            # Check MFA if the site requires it or the user has it setup
            if not user_is_enrolled:
                # Not setup, yet is required.
                # Kick to MFA creation screen
                alert(
                    request,
                    "MFA is required to authenticate, yet you don't have it set up. "
                    "Please set it up here.",
                    level="error",
                )
                return Redirect(request.url_for("create_totp_mfa"))

            # Attempt to authenticate against the MFA provider
            if not await constants.MFA_TOTP_PROVIDER.authenticate_user(
                user=user,
                code=mfa_code,
            ):
                return False

        return None

    @get("/sign_in/select_provider", name="select_auth_provider")
    async def get_select_auth_provider(
        self, request: Request, next_route: str = "/"
    ) -> Template:
        return self._render_template(
            request,
            "auth/select_provider.jinja",
            {
                "next_route": next_route,
                "has_oauth": constants.HAS_IMPLEMENTED_OAUTH,
                "has_registration": constants.ALLOW_REGISTRATION,
                "has_magic_link": constants.HAS_IMPLEMENTED_MAGIC_LINK,
            },
        )

    @get("/sign_in/magic_link", name="sign_in_email")
    async def magic_link_get(
        self,
        request: Request,
        next_route: str = "/",
    ) -> Template:
        return self._render_template(
            request,
            "auth/sign_in_email.jinja",
            {"next_route": next_route},
        )

    @post("/sign_in/magic_link")
    async def magic_link_post(
        self,
        request: Request,
        next_route: str = "/",
    ) -> Template | Redirect:
        body: typing.Any = request.scope.get("form")  # type: ignore

        if not body:
            try:
                body = await request.json()
            except SerializationException:
                body = await request.form()

        email = body.get("email", None)
        if email is None:
            alert(request, "Please provide an email", level="error")
            return Redirect(request.url_for("sign_in_email"))

        if not constants.SIMPLE_EMAIL_REGEX.match(email):
            alert(request, "Please enter a valid email.", level="error")
            return Redirect(request.url_for("sign_in_email"))

        user_exists = await Users.exists().where(Users.username == email)  # type: ignore
        if not constants.ALLOW_REGISTRATION and not user_exists:
            alert(
                request, "Sorry, we currently don't allow registration", level="error"
            )
            return Redirect(request.url_for("sign_in_email"))

        if constants.USE_CF_TURNSTILE:
            result = await self.do_turnstile_checks(request)
            if result is not None:
                return result

        await AuthenticationAttempts.create_via_email(email, "magic_link")
        if await AuthenticationAttempts.has_exceeded_limits(
            email, self.account_lockout_limit, self.account_lockout_period
        ):
            alert(
                request,
                "Your authentication attempt is being rate limited. Please try again later.",
                level="error",
            )
            return self._render_template(
                request,
                "auth/sign_in_email.jinja",
                {"next_route": next_route},
                status_code=429,
            )

        magic_link = MagicLinks(
            email=email,
            token=MagicLinks.generate_token(),
            cookie=MagicLinks.generate_token(),
        )
        await magic_link.save()
        back_url = (
            request.url_for("sign_in_email_callback")
            + f"?next_route={next_route}&token={magic_link.token}"
        )
        await send_email(
            email,
            "Sign In Link",
            html=f"Click the following link to sign in: {back_url}",
        )
        alert(
            request,
            "I've sent you an email to sign in, please go and click it.",
            level="success",
        )
        response = Redirect(request.url_for("sign_in_email"))
        response.set_cookie(
            key="magic_link_token",
            value=magic_link.cookie,
            httponly=True,
            secure=constants.IS_PRODUCTION,
            max_age=int(self.max_session_expiry.total_seconds()),
            samesite="lax",
        )
        return response

    @get("/sign_in/magic_link/callback", name="sign_in_email_callback")
    async def magic_link_token_get(
        self,
        request: Request,
        token: str,
        next_route: str = "/",
    ) -> Template | Redirect:
        magic_link: MagicLinks = await MagicLinks.objects().get(
            (MagicLinks.token == token) & (MagicLinks.used_at.is_null())
        )
        if not magic_link or (magic_link and magic_link.is_still_valid is False):
            alert(request, "Sorry that's an invalid token", level="error")
            return Redirect(request.url_for("sign_in_email"))

        user_exists = await Users.exists().where(Users.username == magic_link.email)  # type: ignore

        return self._render_template(
            request,
            "auth/sign_in_email_callback.jinja",
            {"email": magic_link.email, "requires_info": not user_exists},
        )

    @post("/sign_in/magic_link/callback")
    async def magic_link_token_post(
        self, request: Request, token: str, next_route: str = "/"
    ) -> Redirect | Template:
        async with MagicLinks._meta.db.transaction():
            magic_link: MagicLinks = (
                await MagicLinks.objects()
                .lock_rows("NO KEY UPDATE", nowait=True)
                .get((MagicLinks.token == token) & (MagicLinks.used_at.is_null()))
            )
            if not magic_link or (magic_link and magic_link.is_still_valid is False):
                alert(request, "Sorry that's an invalid token", level="error")
                return Redirect(request.url_for("sign_in_email"))

            if request.cookies.get("magic_link_token") == magic_link.cookie:
                magic_link.used_in_same_request_browser = True

            user = await Users.objects().get(Users.username == magic_link.email)  # type: ignore
            if not user:
                body = await request.form()
                name = body.get("name", None)
                failed = False
                if name is None or not name:
                    alert(
                        request, "Sorry but we need your name to proceed", level="error"
                    )
                    failed = True

                if failed:
                    return self._render_template(
                        request,
                        "auth/sign_in_email_callback.jinja",
                        {"email": magic_link.email, "requires_info": True},
                        status_code=400,
                    )

                user = Users(
                    username=magic_link.email,
                    name=name,
                    email=magic_link.email,
                    password=secrets.token_hex(64),
                    active=True,
                    auths_without_password=True,
                )

            user.last_login = utc_now()
            await user.save()

            magic_link.used_at = utc_now()
            await magic_link.save()

        alert(request, "Thanks for signing in", level="success")

        next_route = self.validate_next_route(next_route)

        response: Redirect = Redirect(next_route)
        cookie = await self.create_session_for_user(user)
        response.set_cookie(
            key=self.cookie_name,
            value=cookie,
            httponly=True,
            secure=constants.IS_PRODUCTION,
            max_age=int(self.max_session_expiry.total_seconds()),
            samesite="lax",
        )
        response.delete_cookie("magic_link_token")
        return response

    @get("/sign_in/credentials", name="sign_in")
    async def sign_in_get(self, request: Request, next_route: str = "/") -> Template:
        return self._render_template(
            request,
            "auth/sign_in.jinja",
        )

    @post("/sign_in/credentials")
    async def sign_in_post(
        self,
        request: Request,
        next_route: str = "/",
    ) -> Template | Redirect:
        username, password, mfa = await self.details_from_body(request)

        if constants.USE_CF_TURNSTILE:
            result = await self.do_turnstile_checks(request)
            if result is not None:
                return result

        await AuthenticationAttempts.create_via_username(username, "credentials")
        if await AuthenticationAttempts.has_exceeded_limits(
            username, self.account_lockout_limit, self.account_lockout_period
        ):
            alert(
                request,
                "Your authentication attempt is being rate limited. Please try again later.",
                level="error",
            )
            return self._render_template(request, "auth/sign_in.jinja", status_code=429)

        user, response = await self.get_user_for_creds(request, username, password)
        if response is not None:
            return response

        response = await self.confirm_mfa_was_correct(request, user, mfa)
        if response is False:
            alert(
                request,
                "The username, password or mfa is incorrect.",
                level="error",
            )
            return self._render_template(request, "auth/sign_in.jinja", status_code=401)

        elif response is not None:
            return response

        if constants.CHECK_PASSWORD_AGAINST_HIBP and await has_password_been_pwned(
            password
        ):
            alert(
                request,
                "Your password appears in breach databases, consider changing it.",
                level="error",
            )

        next_route = self.validate_next_route(next_route)

        response: Redirect = Redirect(next_route)
        cookie = await self.create_session_for_user(user)
        response.set_cookie(
            key=self.cookie_name,
            value=cookie,
            httponly=True,
            secure=constants.IS_PRODUCTION,
            max_age=int(self.max_session_expiry.total_seconds()),
            samesite="lax",
        )
        return response

    @get("/mfa/totp", name="manage_totp_mfa", middleware=[EnsureAuth])
    async def totp_mfa_get(self, request: Request) -> Template:
        if await constants.MFA_TOTP_PROVIDER.is_user_enrolled(request.user):
            # MFA must be explicitly deleted before we will allow another one to be configured
            return self._render_template(request, "auth/mfa_configure.jinja")

        return self._render_template(
            request,
            "auth/mfa_create.jinja",
        )

    @get("/mfa/totp/create", name="create_totp_mfa", middleware=[])
    async def totp_mfa_create_get(self, request: Request) -> Template | Redirect:
        if request.user and await constants.MFA_TOTP_PROVIDER.is_user_enrolled(
            request.user
        ):
            alert(
                request,
                "MFA must be explicitly deleted before we will "
                "allow another one to be configured",
                level="error",
            )
            return Redirect(request.url_for("manage_totp_mfa"))

        return self._render_template(
            request,
            "auth/mfa_create.jinja",
        )

    @post("/mfa/totp/create")
    async def totp_mfa_create(self, request: Request) -> Template | Redirect:
        if constants.USE_CF_TURNSTILE:
            result = await self.do_turnstile_checks(request)
            if result is not None:
                return result

        username, password, _ = await self.details_from_body(request)
        user, response = await self.get_user_for_creds(request, username, password)
        if response is not None:
            return response

        if await constants.MFA_TOTP_PROVIDER.is_user_enrolled(user):
            alert(request, "You are already enrolled with MFA.", level="warning")
            return Redirect(request.url_for("manage_totp_mfa"))

        registration_json = await constants.MFA_TOTP_PROVIDER.get_registration_json(
            user
        )
        response = html_template("auth/mfa_confirm.jinja", registration_json)
        cookie = await self.create_session_for_user(user)
        response.set_cookie(
            key=self.cookie_name,
            value=cookie,
            httponly=True,
            secure=constants.IS_PRODUCTION,
            max_age=int(self.max_session_expiry.total_seconds()),
            samesite="lax",
        )
        return response

    @post("/mfa/totp/confirm", name="mfa_totp_confirm", middleware=[EnsureAuth])
    async def totp_mfa_confirm(self, request: Request) -> Template | Redirect:
        _, _, mfa = await self.details_from_body(request)
        response = await self.confirm_mfa_was_correct(request, request.user, mfa)
        if response is False:
            alert(
                request,
                "Looks like your MFA code was wrong. You should "
                "delete it below otherwise you could lock yourself out of your account.",
                level="error",
            )
            return Redirect(request.url_for("manage_totp_mfa"))

        elif response is not None:
            return response

        alert(
            request,
            "MFA was correct, congrats on successfully configuring it!",
            level="success",
        )
        return self._render_template(request, "auth/mfa_configure.jinja")

    @post("/mfa/totp/delete", name="mfa_totp_delete", middleware=[EnsureAuth])
    async def totp_mfa_delete(self, request: Request) -> Template | Redirect:
        form = await request.form()
        password = form.get("password")
        algorithm, iterations_, salt, hashed = Users.split_stored_password(
            request.user.password
        )
        iterations = int(iterations_)
        if not Users.hash_password(password, salt, iterations) == request.user.password:
            alert(
                request,
                "Incorrect password, unable to delete MFA at this time",
                level="error",
            )
            return Redirect(request.url_for("manage_totp_mfa"))

        # SOFT delete, but safe to stack for same user
        await constants.MFA_TOTP_PROVIDER.delete_registration(user=request.user)
        alert(
            request,
            "Successfully deleted MFA for your account, please re-authenticate",
            level="success",
        )
        await self.logout_current_user(request)
        response = Redirect(request.url_for("manage_totp_mfa"))
        response.set_cookie(self.cookie_name, "", max_age=0)
        return response

    @classmethod
    async def logout_current_user(cls, request: Request) -> Redirect:
        cookie = request.cookies.get(cls.cookie_name, None)
        if not cookie:
            # Meh this is fine, just redirect it to home
            return Redirect("/")

        await cls.session_table.remove_session(token=cookie)

        response: Redirect = Redirect(
            cls.default_redirect_to, status_code=HTTP_303_SEE_OTHER
        )
        response.set_cookie(cls.cookie_name, "", max_age=0)
        return response

    @get("/sign_out", name="sign_out")
    async def sign_out_get(self, request: Request) -> Template:
        return self._render_template(request, "auth/sign_out.jinja")

    @post("/sign_out")
    async def sign_out_post(self, request: Request) -> Redirect:
        from web.controllers.oauth_controller import DISCORD_OAUTH

        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        await DISCORD_OAUTH.clear_user_guilds(oauth_entry.oauth_id)
        await DISCORD_OAUTH.revoke_token(oauth_entry.refresh_token, "refresh_token")
        return await self.logout_current_user(request)

    @get("/passwords/forgot", name="forgot_password")
    async def forgot_password_get(self, request: Request) -> Template:
        alert(
            request,
            "This functionality hasn't been implemented yet. "
            "Reach out to your administrator directly.",
            level="info",
        )
        return self._render_template(request, "auth/forgot_password.jinja")

    @post("/passwords/forgot")
    async def forgot_password_post(self, request: Request) -> Redirect:
        # TODO CF Turnstile copy paste
        return Redirect(request.url_for("forgot_password"))

    @get(
        "/details/change",
        name="change_details",
        middleware=[EnsureAuth],
    )
    async def get_change_details(self, request: Request) -> Template:
        return self._render_template(request, "auth/change_details.jinja")

    @post(
        "/details/change",
        middleware=[EnsureAuth],
    )
    async def post_change_details(self, request: Request) -> Template:
        body = await request.form()
        name = body.get("name")
        if not name:
            alert(request, "Setting a name is required", level="error")
            return self._render_template(
                request, "auth/change_details.jinja", status_code=400
            )

        phone = body.get("phone")
        signed_up_for_newsletter = body.get("newsletter") == "on"
        request.user.name = name
        request.user.phone_number = phone
        request.user.signed_up_for_newsletter = signed_up_for_newsletter
        await request.user.save()
        alert(request, "Thanks, I have saved your details", level="success")
        return self._render_template(request, "auth/change_details.jinja")

    @get(
        "/passwords/change",
        name="change_password",
        middleware=[EnsureAuth],
    )
    async def change_password_get(self, request: Request) -> Template:
        return self._render_template(request, "auth/change_password.jinja")

    @post("/passwords/change", middleware=[EnsureAuth])
    async def change_password_post(self, request: Request) -> Template | Redirect:
        # Some middleware (for example CSRF) has already awaited the request
        # body, and adds it to the request.
        body: typing.Any = request.scope.get("form")  # type: ignore

        if not body:
            try:
                body = await request.json()
            except SerializationException:
                body = await request.form()

        current_password = body.get("current_password")
        new_password = body.get("new_password")
        new_password_again = body.get("new_password_again")

        if (
            current_password is None
            or new_password is None
            or new_password_again is None
        ):
            alert(request, "Please fill in all form fields.", level="error")
            return Redirect(request.url_for("change_password"))

        if not hmac.compare_digest(new_password, new_password_again):
            alert(request, "New password fields did not match.", level="error")
            return Redirect(request.url_for("change_password"))

        user = typing.cast(Users, request.user)
        algorithm, iterations_, salt, hashed = Users.split_stored_password(
            user.password
        )
        iterations = int(iterations_)
        if Users.hash_password(current_password, salt, iterations) != user.password:
            alert(request, "Your current password was wrong.", level="error")
            return Redirect(request.url_for("change_password"))

        if constants.CHECK_PASSWORD_AGAINST_HIBP and await has_password_been_pwned(
            new_password
        ):
            alert(
                request,
                "Your new password appears in breach databases, "
                "please pick a unique password.",
                level="error",
            )
            return Redirect(request.url_for("change_password"))

        await user.update_password(user.id, new_password)
        alert(
            request,
            "Successfully changed password, please reauthenticate.",
            level="success",
        )
        return await self.logout_current_user(request)

    @get("/sign_up", name="sign_up")
    async def sign_up_get(self, request: Request) -> Template:
        alert(
            request,
            "Manual sign ups are disabled. This will do nothing.",
            level="warning",
        )
        return self._render_template(
            request,
            "auth/sign_up.jinja",
        )

    @post("/sign_up")
    async def sign_up_post(
        self,
        request: Request,
    ) -> Template | Redirect:
        return Redirect(request.url_for("sign_up"))
