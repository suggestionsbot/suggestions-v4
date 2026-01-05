from unittest.mock import AsyncMock

import hikari

from shared.tables import QueuedSuggestions


async def test_as_embed():
    bot = AsyncMock(spec=hikari.GatewayBot)
    raise ValueError("TODO Implement this test")
