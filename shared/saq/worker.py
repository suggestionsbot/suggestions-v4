# ruff: noqa: T201
import functools
import datetime
import os
from typing import cast

import saq
from dotenv import load_dotenv
from opentelemetry import trace, propagate
from opentelemetry.metrics import get_meter_provider
from piccolo_api.session_auth.tables import SessionsBase
from saq import Queue, Job
from saq.types import Context

from web import constants
from web.tables import APIToken
from web.util.table_mixins import utc_now
from bot.constants import OTEL_TRACER

load_dotenv()


def traced_task(fn):  # noqa: ANN001, ANN201
    @functools.wraps(fn)  # SAQ registers by __name__ — keep it
    async def wrapper(ctx: Context, **kwargs):  # noqa: ANN003, ANN202
        job = ctx["job"]
        carrier = job.meta.get("otel") or {}
        parent = propagate.extract(carrier) if carrier else None
        with OTEL_TRACER.start_as_current_span(
            job.function,
            context=parent,
            kind=trace.SpanKind.CONSUMER,
        ) as span:
            span.set_attribute("messaging.system", "saq")
            span.set_attribute("messaging.message.id", job.key)
            span.set_attribute("saq.job.attempts", job.attempts)
            span.set_attribute("saq.job.retries", job.retries)
            span.set_attribute("saq.job.timeout", job.timeout)
            span.set_attribute("saq.job.id", job.id)
            return await fn(ctx, **kwargs)

    return wrapper


@traced_task
async def tick(_: Context) -> None:
    print(f"tick {utc_now()}")


@traced_task
async def log_current_valid_sessions(_: Context) -> None:
    meter = get_meter_provider().get_meter("users.sessions")
    session_counter = meter.create_up_down_counter(
        name="current_valid_user_sessions",
        description="Total number of currently valid User sessions",
    )
    count = await SessionsBase.count(distinct=[SessionsBase.user_id]).where(
        datetime.datetime.now() < SessionsBase.expiry_date  # noqa: DTZ005
    )
    session_counter.add(count)


@traced_task
async def log_current_api_tokens(_: Context) -> None:
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


async def enqueue_traced(queue: Queue, function: str, **kwargs) -> Job | None:
    with OTEL_TRACER.start_as_current_span(
        f"queuing '{function}'", kind=trace.SpanKind.PRODUCER
    ):
        carrier: dict[str, str] = {}
        propagate.inject(carrier)  # writes traceparent/tracestate
        kwargs["meta"] = {**kwargs.get("meta", {}), "otel": carrier}
        return await queue.enqueue(function, **kwargs)


async def before_process(ctx: Context) -> None:
    print(f"Starting job: {ctx['job'].function}\n\tWith kwargs: {ctx['job'].kwargs}")
    job: saq.Job = ctx["job"]
    job.retries = 0
    job.timeout = SAQ_TIMEOUT
    await job.update(timeout=SAQ_TIMEOUT)


async def after_process(ctx: Context) -> None:
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
            message="Observed an error in the following saq function: "
            f"`{ctx['job'].function!r}`",
            internal_error_reference=internal_error,
            tags="warning",
        )


async def startup(_: Context) -> None:
    # Ensure logger is started in SAQ process
    constants.configure_otel(constants.DASHBOARD_SERVICE_NAME)
    await constants.DISCORD_REST_CLIENT.start()
    await SAQ_QUEUE.enqueue("log_current_valid_sessions")
    await SAQ_QUEUE.enqueue("log_current_api_tokens")
    await SAQ_QUEUE.enqueue("populate_sid_autocomplete")
    await SAQ_QUEUE.enqueue("compute_aggregate_command_invokes")


async def shutdown(_: Context) -> None:
    await constants.DISCORD_REST_CLIENT.close()


SAQ_TIMEOUT = int(datetime.timedelta(hours=1).total_seconds())
SAQ_QUEUE = Queue.from_url(os.environ.get("REDIS_URL", ""), name="shared")
