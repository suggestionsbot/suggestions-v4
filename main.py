import asyncio
import os

import hikari
from dotenv import load_dotenv

from bot import create_bot

load_dotenv()


async def main():
    bot, client = await create_bot(token=os.environ["BOT_TOKEN"])

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
