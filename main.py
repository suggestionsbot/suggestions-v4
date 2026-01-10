import asyncio
import logging
import os
from pathlib import Path

import commons
import hikari
import lightbulb
from dotenv import load_dotenv

from bot import create_bot
from bot.constants import VERSION
from shared.tables import GuildConfigs
from web import constants as t_constants

load_dotenv()
logger = logging.getLogger(__name__)
t_constants.configure_otel(t_constants.BOT_SERVICE_NAME)


async def main():
    try:
        await GuildConfigs.count()
    except:
        print(
            "Please run migrate, DB does not exist!\n"
            "N.b. May need to delete the migrations table first."
        )
        exit(1)

    bot, client = await create_bot(
        token=t_constants.get_secret("BOT_TOKEN", t_constants.infisical_client),
        base_path=Path("bot"),
    )

    @client.error_handler
    async def handler(
        exc: lightbulb.exceptions.ExecutionPipelineFailedException,
    ) -> bool:
        logger.critical(
            "Unhandled error encountered",
            extra={
                "error.name": exc.causes[0].__class__.__name__,
                "traceback": commons.exception_as_string(exc.causes[0]),
            },
        )
        return False

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
