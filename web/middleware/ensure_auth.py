from __future__ import annotations

from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from piccolo_api.session_auth.tables import SessionsBase

from web.exception_handlers import RedirectForAuth
from web.tables import Users, APIToken
from web.util import alert


class EnsureAuth(AbstractAuthenticationMiddleware):
    session_table = SessionsBase
    auth_table = Users
    cookie_name = "id"
    admin_only = False
    superuser_only = False
    active_only = True
    increase_expiry = None
    requires_auth = True

    @classmethod
    async def get_user_from_connection(
        cls,
        connection: ASGIConnection | Request,
        possible_redirect: str = "/",
        *,
        fail_on_not_set: bool = True,
    ) -> Users | None:
        token = connection.cookies.get(cls.cookie_name, None)
        if not token:
            if fail_on_not_set:
                alert(connection, "Please authenticate to view this resource")
                raise RedirectForAuth(possible_redirect)

            return None

        user_id = await cls.session_table.get_user_id(
            token, increase_expiry=cls.increase_expiry
        )

        if not user_id:
            if fail_on_not_set:
                alert(connection, "Please authenticate to view this resource")
                raise RedirectForAuth(possible_redirect)

            return None

        return (
            await cls.auth_table.objects()
            .where(cls.auth_table._meta.primary_key == user_id)
            .first()
            .run()
        )

    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        if not self.requires_auth:
            return AuthenticationResult(user=None, auth=None)

        possible_redirect = (
            f"{connection.url.path}?{connection.url.query}"
            if connection.url.query
            else connection.url.path
        )
        piccolo_user = await self.get_user_from_connection(
            connection, possible_redirect
        )

        if not piccolo_user:
            raise NotAuthorizedException("That user doesn't exist")

        if self.admin_only and not piccolo_user.admin:
            raise NotAuthorizedException("Admin users only")

        if self.superuser_only and not piccolo_user.superuser:
            raise NotAuthorizedException("Superusers only")

        if self.active_only and not piccolo_user.active:
            raise NotAuthorizedException("Active users only")

        return AuthenticationResult(user=piccolo_user, auth=None)


class EnsureAdmin(EnsureAuth):
    admin_only = True


class EnsureSuperUser(EnsureAdmin):
    superuser_only = True


# noinspection PyMethodMayBeStatic
class UserFromAPIKey(AbstractAuthenticationMiddleware):
    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        raw_token = connection.headers.get("X-API-KEY")
        if not raw_token:
            raise NotAuthorizedException("This route requires an API Token")

        if not await APIToken.validate_token_is_valid(raw_token):
            raise NotAuthorizedException("This token is expired")

        api_token = await APIToken.get_instance_from_token(raw_token)
        return AuthenticationResult(user=api_token.user, auth=api_token)
