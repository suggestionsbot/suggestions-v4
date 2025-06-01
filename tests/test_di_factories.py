from unittest.mock import AsyncMock

import lightbulb

from bot.bot import create_guild_config, create_user_config
from bot.tables import GuildConfigs, UserConfigs


# noinspection PyPropertyAccess
async def test_get_guild_config():
    r_1 = await GuildConfigs.count()
    assert r_1 == 0

    ctx: lightbulb.Context = AsyncMock(spec=lightbulb.Context)
    ctx.guild_id = 12345
    await create_guild_config(ctx)

    r_2 = await GuildConfigs.count()
    assert r_2 == 1


# noinspection PyPropertyAccess
async def test_get_user_config():
    r_1 = await UserConfigs.count()
    assert r_1 == 0

    ctx: lightbulb.Context = AsyncMock(spec=lightbulb.Context)
    ctx.user.id = 12345
    await create_user_config(ctx)

    r_2 = await UserConfigs.count()
    assert r_2 == 1
