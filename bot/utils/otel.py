import lightbulb
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal

import orjson
from fastnanoid import generate
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Status, StatusCode

from bot import utils
from bot.constants import OTEL_TRACER
from bot.tables import InternalErrors
from shared.utils.ntfy import notify_ethan_of_something
from web import constants


@asynccontextmanager
async def start_error_span(  # noqa: ANN201 #I Dont know how to type this
    base_exception: Exception,
    span_name: Literal[
        "global error handler",
        "command error handler",
        "modal error handler",
        "component error handler",
    ],
    *,
    command_name: str,
    guild_id: int | None = None,
    user_id: int | None = None,
):
    with OTEL_TRACER.start_as_current_span(span_name) as child:
        internal_error: InternalErrors = await InternalErrors.persist_error(
            base_exception,
            command_name=command_name,
            guild_id=guild_id,
            user_id=user_id,
        )
        child.set_attribute("error.name", base_exception.__class__.__name__)
        if not utils.should_handle_error(base_exception):
            # all these we dont need to care about being logged
            # as we handle them enough for end us`ers to
            # theoretically fix themselves
            child.set_attribute("error.handled", value=True)

        else:
            # We want to propagate these as 'unhandled errors'
            # that should be taken a look at by a dev
            child.set_attribute("error.handled", value=False)
            child.set_status(Status(StatusCode.ERROR))
            child.record_exception(base_exception)
            await notify_ethan_of_something(
                title="Unknown Error",
                message=f"Observed an unhandled error in `{command_name!r}`",
                internal_error_reference=internal_error,
                tags="warning",
            )

        yield internal_error


def get_trace_id() -> str:
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    return format(span_context.trace_id, "032x")


async def generate_trace_link_state() -> str:
    link_id: str = generate(size=30)
    data = {}
    constants.OTEL_PROPAGATOR.inject(data)
    await constants.REDIS_CLIENT.set(
        f"trace_context:{link_id}",
        orjson.dumps(data),
        ex=timedelta(days=1),
    )
    return link_id


async def get_context_from_link_state(link_id: str) -> Context | None:
    raw_data = await constants.REDIS_CLIENT.get(f"trace_context:{link_id}")
    if raw_data is None:
        return None

    data = orjson.loads(raw_data)
    return constants.OTEL_PROPAGATOR.extract(data)
