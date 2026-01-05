import datetime

from litestar import Controller, post, Request, Response, delete
from litestar.di import Provide
from pydantic import BaseModel, Field

from web.crud.controller import CRUD_BASE_OPENAPI_RESPONSES
from web.di import retrieve_api_key
from web.exception_handlers import APIRedirectForAuth
from web.guards import ensure_api_token
from web.middleware import EnsureAuth
from web.tables import APIToken


class TokenInModel(BaseModel):
    token: str = Field(description="Your current API Token")


class TokenOutModel(BaseModel):
    token: str = Field(description="Your current API Token")
    expiry_date: datetime.datetime = Field(description="When this token is scheduled to expire")
    max_expiry_date: datetime.datetime = Field(
        description="The maximum time that this token validity can be extended until"
    )


class APIAuthTokenController(Controller):
    path = "/auth/token"
    token_expiry = datetime.timedelta(hours=2)
    max_token_expiry = datetime.timedelta(days=3)
    tags = ["Authentication"]

    @post(
        "/initial",
        name="new_api_token_using_session",
        security=[{"session": []}],
        responses=CRUD_BASE_OPENAPI_RESPONSES,
        middleware=[EnsureAuth],
        description="Create a new API token using a valid website session",
    )
    async def post_token_new(self, request: Request) -> TokenOutModel:
        api_token = await APIToken.create_api_token(
            request.user, self.token_expiry, self.max_token_expiry
        )
        return TokenOutModel(
            token=api_token.token,
            expiry_date=api_token.expiry_date,
            max_expiry_date=api_token.max_expiry_date,
        )

    @post(
        "/refresh",
        exclude_from_csrf=True,
        status_code=200,
        guards=[ensure_api_token],
        dependencies={"token": Provide(retrieve_api_key)},
        security=[{"apiKey": []}],
        responses=CRUD_BASE_OPENAPI_RESPONSES,
        description="Create a new API token using an existing API Key",
    )
    async def post_fresh_token(
        self, request: Request, token: str
    ) -> Response[APIRedirectForAuth | TokenOutModel]:
        api_token: APIToken | None = await APIToken.get_token(  # type: ignore
            token,
            increase_window=self.token_expiry,
            expiry_window=self.token_expiry,
            max_expiry_window=self.max_token_expiry,
        )
        if api_token is None:
            return Response(
                APIRedirectForAuth(
                    redirect_uri=request.url_for("new_api_token_using_session"),
                    status_code=401,
                    message=(
                        "You are attempting to access an authenticated "
                        "resource without providing authentication."
                    ),
                ),
                status_code=401,
            )

        return Response(
            TokenOutModel(
                token=api_token.token,
                expiry_date=api_token.expiry_date,
                max_expiry_date=api_token.max_expiry_date,
            ),
            status_code=200,
        )

    @delete(
        "/",
        exclude_from_csrf=True,
        status_code=200,
        guards=[ensure_api_token],
        dependencies={"token": Provide(retrieve_api_key)},
        security=[{"apiKey": []}],
        responses=CRUD_BASE_OPENAPI_RESPONSES,
        description="Invalidate a given API token",
    )
    async def invalidate_token(self, token: str) -> None:
        await APIToken.delete_token(token)
        return None
