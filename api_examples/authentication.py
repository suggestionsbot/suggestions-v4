from pydantic import BaseModel, field_validator, ConfigDict
from typing import Self, Any, Final
import asyncio

import arrow
import commons.timing
import httpx


class ExpiredTokenError(Exception):
    """Token has expired."""


class UserModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    user_id: int
    email: str
    last_login: arrow.Arrow

    @field_validator("last_login", mode="before")
    @classmethod
    def set_last_login(cls, v: Any) -> Any:
        if isinstance(v, str):
            return arrow.get(v)
        return None


class TokenModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    token: str
    expiry_date: arrow.Arrow
    max_expiry_date: arrow.Arrow

    @field_validator("expiry_date", mode="before")
    @classmethod
    def set_expiry(cls, v: Any) -> Any:
        if isinstance(v, str):
            return arrow.get(v)
        return None

    @field_validator("max_expiry_date", mode="before")
    @classmethod
    def set_max_expiry(cls, v: Any) -> Any:
        if isinstance(v, str):
            return arrow.get(v)
        return None


class APIAuth:
    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._current_token: TokenModel | None = None
        self._client: httpx.AsyncClient | None = client
        self._api_key_header: Final[str] = "X-API-KEY"

    def use_client(self, client: httpx.AsyncClient) -> Self:
        self._client = client
        return self

    @property
    def token(self) -> str | None:
        """The current API token."""
        if self._current_token is not None:
            return self._current_token.token
        return None

    async def create_initial_token(self, website_session: str) -> None:
        """Creates a new API token using a website session.

        It is unexpected to do this as the
        Dashboard provides the initial API token.

        Notes
        -----
        Call renew_token before expiry_date
        otherwise your token will expire.

        """
        assert self._client is not None, "Expected client to exist"
        resp = await self._client.post(
            "/auth/token/initial", cookies={"id": website_session}
        )
        if resp.status_code == httpx.codes.UNAUTHORIZED:
            msg = "Invalid credentials."
            raise ValueError(msg)

        self._current_token = TokenModel(**resp.json())

    async def renew_token(self) -> None:
        """Renews the current API token.

        Notes
        -----
        Call renew_token before expiry_date
        otherwise your token will expire.

        """
        assert self._client is not None, "Expected client to exist"
        assert self._current_token is not None, "Expected API token to exist"
        resp = await self._client.post(
            "/auth/token/refresh",
            headers={self._api_key_header: self._current_token.token},
        )
        if resp.status_code == httpx.codes.UNAUTHORIZED:
            msg = "Invalid credentials."
            raise ValueError(msg)

        self._current_token = TokenModel(**resp.json())

    async def invalidate_token(self) -> None:
        """Invalidates the current API token."""
        assert self._client is not None, "Expected client to exist"
        assert self._current_token is not None, "Expected API token to exist"
        resp = await self._client.delete(
            "/auth/token", headers={self._api_key_header: self._current_token.token}
        )
        if resp.status_code not in (httpx.codes.OK, httpx.codes.UNAUTHORIZED):
            msg = f"Invalidation failed with response code {resp.status_code}."
            raise ValueError(msg)

    async def fetch_me(self) -> UserModel:
        """Fetches the user associated with the current API token."""
        assert self._current_token is not None, "Expected API token to exist"
        assert self._client is not None, "Expected client to exist"
        resp = await self._client.get(
            "/auth/token/me", headers={self._api_key_header: self._current_token.token}
        )
        if resp.status_code == httpx.codes.UNAUTHORIZED:
            msg = "Invalid credentials."
            raise ValueError(msg)

        return UserModel(**resp.json())


async def main() -> None:
    website_session = "y6eskF9Q8cuWgQCpjQEZhWRb1nNYdlTwBSujzlvmHNQ"

    base_url = "http://127.0.0.1:2300"
    # TODO Change to this in production
    # base_url = "https://dashboard.suggestions.gg"
    async with httpx.AsyncClient(base_url=base_url) as client:
        api_auth = APIAuth(client=client)
        await api_auth.create_initial_token(website_session)
        await api_auth.renew_token()
        print(api_auth.token)
        me = await api_auth.fetch_me()
        # await api_auth.invalidate_token()
        print(me)


if __name__ == "__main__":
    asyncio.run(main())
