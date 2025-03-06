from unittest.mock import AsyncMock

from bot import SuggestionsBot
from bot.utils import InteractionHandler


async def test_ih_redis(
    bot: SuggestionsBot,
    fake_interaction: AsyncMock,
) -> None:
    """Tests that the interaction can store and reload from redis"""
    r_1 = await bot.redis.get(f"IH:{fake_interaction.id}")
    assert r_1 is None
    ih_1 = await InteractionHandler.new_handler(fake_interaction, with_message=False)
    r_2 = await bot.redis.get(f"IH:{fake_interaction.id}")
    assert r_2 is not None

    ih_2 = await InteractionHandler.fetch_handler(fake_interaction)
    assert ih_2.ephemeral == ih_1.ephemeral
    assert ih_2.with_message == ih_1.with_message
    assert ih_2.is_deferred == ih_1.is_deferred
