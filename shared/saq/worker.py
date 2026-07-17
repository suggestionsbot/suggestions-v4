import datetime
import os
from typing import cast

import saq
from dotenv import load_dotenv
from opentelemetry.metrics import get_meter_provider
from piccolo_api.session_auth.tables import SessionsBase
from saq import Queue
from saq.types import Context

from web import constants
from web.tables import APIToken
from web.util.table_mixins import utc_now

load_dotenv()


async def tick(_):
    print(f"tick {datetime.datetime.now(datetime.timezone.utc)}")


async def log_current_valid_sessions(_):
    meter = get_meter_provider().get_meter("users.sessions")
    session_counter = meter.create_up_down_counter(
        name="current_valid_user_sessions",
        description="Total number of currently valid User sessions",
    )
    count = await SessionsBase.count(distinct=[SessionsBase.user_id]).where(
        datetime.datetime.now() < SessionsBase.expiry_date
    )
    session_counter.add(count)


async def log_current_api_tokens(_):
    meter = get_meter_provider().get_meter("users.api_tokens")
    session_counter = meter.create_up_down_counter(
        name="current_valid_api_tokens",
        description="Total number of currently valid API tokens",
    )
    count = (
        await APIToken.count(distinct=[APIToken.user])
        .where(utc_now() < APIToken.expiry_date)
        .where()
    )
    session_counter.add(count)


async def before_process(ctx):
    print(f"Starting job: {ctx['job'].function}\n\tWith kwargs: {ctx['job'].kwargs}")
    job: saq.Job = ctx["job"]
    job.retries = 0
    job.timeout = SAQ_TIMEOUT


async def after_process(ctx: Context):
    print(f"Finished job: {ctx['job'].function}\n\tWith kwargs: {ctx['job'].kwargs}")
    if "exception" in ctx:
        from bot.tables import InternalErrors
        from shared.utils.ntfy import notify_ethan_of_something

        internal_error: InternalErrors = await InternalErrors.persist_error(
            cast("Exception", ctx["exception"]),
            command_name=ctx["job"].function,
            extra_info=str(ctx["job"].kwargs),
        )
        await notify_ethan_of_something(
            title="SAQ Error",
            message=f"Observed an error in the following saq function: `{ctx["job"].function!r}`",
            internal_error_reference=internal_error,
            tags="warning",
        )


async def startup(_):
    # Ensure logger is started in SAQ process
    constants.configure_otel(constants.DASHBOARD_SERVICE_NAME)
    await constants.DISCORD_REST_CLIENT.start()
    await SAQ_QUEUE.enqueue("log_current_valid_sessions")
    await SAQ_QUEUE.enqueue("log_current_api_tokens")
    await SAQ_QUEUE.enqueue("populate_sid_autocomplete")


async def shutdown(_):
    await constants.DISCORD_REST_CLIENT.close()


SAQ_TIMEOUT = int(datetime.timedelta(hours=1).total_seconds())
SAQ_QUEUE = Queue.from_url(os.environ.get("REDIS_URL"), name="shared")
