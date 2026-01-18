import datetime
import os

import saq
from dotenv import load_dotenv
from opentelemetry.metrics import get_meter_provider
from piccolo_api.session_auth.tables import SessionsBase
from saq import CronJob, Queue
from saq.types import SettingsDict

from shared.saq.suggestions import edit_suggestion_message
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


async def after_process(ctx):
    print(f"Finished job: {ctx['job'].function}\n\tWith kwargs: {ctx['job'].kwargs}")


async def startup(_):
    # Ensure logger is started in SAQ process
    constants.configure_otel(constants.DASHBOARD_SERVICE_NAME)
    await SAQ_QUEUE.enqueue("log_current_valid_sessions")
    await SAQ_QUEUE.enqueue("log_current_api_tokens")


SAQ_TIMEOUT = int(datetime.timedelta(hours=1).total_seconds())
SAQ_QUEUE = Queue.from_url(os.environ.get("REDIS_URL"))

SAQ_SETTINGS = SettingsDict(
    queue=SAQ_QUEUE,
    functions=[
        tick,
        log_current_valid_sessions,
        log_current_api_tokens,
        edit_suggestion_message,
    ],
    concurrency=10,
    startup=startup,
    before_process=before_process,
    after_process=after_process,
    # https://crontab.guru
    cron_jobs=[
        # run every 30 seconds
        # CronJob(tick, cron="* * * * * */30"),
        # Once per day, at the top of the day
        CronJob(
            tick,
            cron="0 0 * * */1",
            timeout=SAQ_TIMEOUT,
            retries=1,
        ),
        CronJob(
            log_current_valid_sessions,
            cron="*/5 * * * *",
            timeout=SAQ_TIMEOUT,
            retries=1,
        ),
        CronJob(
            log_current_api_tokens,
            cron="*/5 * * * *",
            timeout=SAQ_TIMEOUT,
            retries=1,
        ),
    ],
)
