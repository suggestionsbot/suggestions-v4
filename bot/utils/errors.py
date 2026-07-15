import asyncio
import inspect
import logging
from types import TracebackType
from typing import Self, Final

import hikari

from bot.exceptions import MessageTooLong, MissingQueueChannel
from bot.tables import InternalErrors
from shared.utils.ntfy import notify_ethan_of_something

logger = logging.getLogger(__name__)


class HandleClientHTTPResponse:
    def __init__(self, caller_name: str, context: str | None = None) -> None:
        self.caller_name = caller_name
        self.context = context

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if exc_val is not None:
            return await self.handle_client_http_response(exc_val)

        return False

    async def handle_client_http_response(self, exc: BaseException) -> bool:
        """Handles the various responses we've seen."""
        if isinstance(exc, hikari.ClientHTTPResponseError) and exc.code == 40005:
            internal_error: InternalErrors = await InternalErrors.persist_error(
                exc,
                command_name=self.caller_name,
                extra_info=self.context,
            )
            await notify_ethan_of_something(
                title="ClientHTTPResponseError",
                message="Observed an unhandled ClientHTTPResponseError. "
                "I have created an error with context",
                internal_error_reference=internal_error,
                tags="warning",
            )
            return True

        return False


IGNORABLE_EXCEPTION_TYPES: tuple[type[Exception], ...] = (
    MessageTooLong,
    MissingQueueChannel,
)
UNKNOWN_INTERACTION: Final[int] = 10062


def should_handle_error(exc: Exception) -> bool:
    """A basic helper to decide if errors should be handled."""
    if isinstance(exc, IGNORABLE_EXCEPTION_TYPES):
        return False

    if (  # noqa: SIM103
        isinstance(exc, hikari.NotFoundError) and exc.code == UNKNOWN_INTERACTION
    ):
        # #It Happens, Ignore It https://github.com/discord/discord-api-docs/issues/5558
        # https://discord.com/channels/574921006817476608/1063575318599835778/1241512673015763096
        logger.debug(
            "Observed hikari.errors.NotFoundError: "
            "Not Found 404: (10062) 'Unknown interaction'"
        )
        return False

    return True


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
