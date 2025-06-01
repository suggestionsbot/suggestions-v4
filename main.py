import asyncio
import os
from pathlib import Path

import hikari
from dotenv import load_dotenv

from bot import create_bot
from bot.constants import INFISICAL_SDK
from bot.tables import GuildConfig

load_dotenv()


async def main():
    try:
        await GuildConfig.count()
    except:
        print(
            "Please run migrate, DB does not exist!\n"
            "N.b. May need to delete the migrations table first."
        )
        exit(1)

    bot, client = await create_bot(
        token=INFISICAL_SDK.get_secret("BOT_TOKEN"),
        base_path=Path("bot"),
    )

    @bot.listen(hikari.StartingEvent)
    async def on_starting(_: hikari.StartingEvent) -> None:
        await client.load_extensions(
            "bot.extensions.suggest",
        )
        await client.start()

    await bot.start()
    await bot.join()


if __name__ == "__main__":
    asyncio.run(main())
