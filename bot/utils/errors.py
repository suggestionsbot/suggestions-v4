from datetime import timedelta

from web.constants import REDIS_CLIENT
import asyncio
import inspect
from types import TracebackType

import hikari
from typing import Self

import httpx


class HandleClientHTTPResponse:
    def __init__(self, caller_name: str) -> None:
        self.caller_name = caller_name

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if exc_val is not None:
            await self.handle_client_http_response(exc_val)
            return True

        return False

    async def handle_client_http_response(self, exc: BaseException) -> None:
        """Handles the various responses we've seen."""
        print(self.caller_name)
        if isinstance(exc, hikari.ClientHTTPResponseError):
            pass


async def fetch_user_avatar(user_id: int, *, rest) -> hikari.URL | None:
    """Fetches the user avatar, returning None if the avatar is not available."""
    data = await REDIS_CLIENT.get(f"avatars/{user_id}")
    if data is not None:
        assert isinstance(data, bytes), "Redis returned a string"
        return hikari.URL(data.decode("utf-8"))

    async with httpx.AsyncClient() as client:
        user: hikari.User = await rest.fetch_user(user_id)
        url = user.display_avatar_url.url
        resp = await client.get(url)
        if resp.status_code != 200:  # noqa: PLR2004
            return None

        await REDIS_CLIENT.set(
            f"avatars/{user_id}",
            url.encode("utf-8"),
            ex=timedelta(hours=12),
        )

    return hikari.URL(url)


async def main():
    # You must use 'async with' to invoke it
    async with HandleClientHTTPResponse(
        inspect.currentframe().f_code.co_name  # ty:ignore[unresolved-attribute]
    ):
        print("Simulating an async operation...")
        await asyncio.sleep(1)
        result = 10 / 0  # Triggers ZeroDivisionError

    print("Program successfully survived the async error.")


if __name__ == "__main__":
    asyncio.run(main())
