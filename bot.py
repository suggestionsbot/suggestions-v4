import asyncio
import logging
from pathlib import Path
from typing import cast

import hikari
import lightbulb
from dotenv import load_dotenv

from bot import create_bot
from bot.constants import CONFIGURE_GROUP, NOTES_GROUP, BLOCKLIST_GROUP
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
        # Force load these so they register on the group
        from bot.extensions.configure_guild import ConfigureGuildCmd  # noqa
        from bot.extensions.notes import NotesAddCmd, NotesRemoveCmd  # noqa
        from bot.extensions.blocklist import BlocklistAddCmd, BlocklistRemoveCmd  # noqa

        client.register(CONFIGURE_GROUP)
        client.register(NOTES_GROUP)
        client.register(BLOCKLIST_GROUP)
        await client.load_extensions(
            "bot.extensions.suggest",
            "bot.tasks.store_guilds_in_redis",
        )
        await client.start()

    await bot.start()
    await bot.join()


if __name__ == "__main__":
    asyncio.run(main())
