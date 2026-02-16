import asyncio
import logging
from pathlib import Path
from typing import cast

import hikari
import lightbulb
from dotenv import load_dotenv

from bot import create_bot
from shared.tables import GuildConfigs
from web import constants as t_constants

load_dotenv()

log_conf = "INFO"
logger = logging.getLogger(__name__)
if t_constants.IS_PRODUCTION:
    log_conf = None
    t_constants.configure_otel(t_constants.BOT_SERVICE_NAME)

elif t_constants.ENFORCE_OTEL:
    log_conf = None
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
        log_conf=log_conf,
    )
    bot = cast(hikari.GatewayBot, bot)
    client = cast(lightbulb.Client, client)

    @bot.listen(hikari.StartingEvent)
    async def on_starting(_: hikari.StartingEvent) -> None:
        await client.load_extensions(
            "bot.extensions.suggest",
            "bot.extensions.configure",
        )
        await client.start()

    await bot.start()
    await bot.join()


if __name__ == "__main__":
    asyncio.run(main())
