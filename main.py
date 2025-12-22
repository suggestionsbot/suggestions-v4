import asyncio
import os
from pathlib import Path

import commons
import hikari
import lightbulb
import logoo
from dotenv import load_dotenv
from logoo import PrimaryLogger

from bot import create_bot
from bot.constants import VERSION
from shared.tables import GuildConfigs
from web import constants as t_constants

load_dotenv()


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

    logger: PrimaryLogger = PrimaryLogger(
        __name__,
        base_url="https://logs.suggestions.gg",
        org="default",
        stream=(
            "test_bot" if commons.value_to_bool(os.environ.get("DEBUG")) else "prod_bot"
        ),
        username=t_constants.get_secret("LOGOO_USER", t_constants.infisical_client),
        password=t_constants.get_secret("LOGOO_PASSWORD", t_constants.infisical_client),
        poll_time=15,
        global_metadata={
            # TODO Readd this later
            # "cluster": bot.cluster_id,
            "bot_version": VERSION,
        },
    )
    await logger.start_consumer()

    @client.error_handler
    async def handler(
        exc: lightbulb.exceptions.ExecutionPipelineFailedException,
    ) -> bool:
        logger.critical(
            "Unhandled error encountered",
            extra_metadata={
                "error_name": exc.causes[0].__class__.__name__,
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
