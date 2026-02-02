from contextlib import contextmanager
from datetime import timedelta
from typing import Literal

import orjson
from fastnanoid import generate
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Status, StatusCode

from bot.constants import OTEL_TRACER
from bot.exceptions import MessageTooLong, MissingQueueChannel
from web import constants

IGNORABLE_EXCEPTION_TYPES: tuple[type[Exception], ...] = (
    MessageTooLong,
    MissingQueueChannel,
)


@contextmanager
def start_error_span(
    base_exception, span_name: Literal["global error handler", "command error handler"]
):
    with OTEL_TRACER.start_as_current_span(span_name) as child:
        child.set_attribute("error.name", base_exception.__class__.__name__)
        if isinstance(base_exception, IGNORABLE_EXCEPTION_TYPES):
            # all these we dont need to care about being logged
            # as we handle them enough for end users to
            # theoretically fix themselves
            child.set_attribute("error.handled", True)

        else:
            # We want to propagate these as 'unhandled errors'
            # that should be taken a look at by a dev
            child.set_attribute("error.handled", False)
            child.set_status(Status(StatusCode.ERROR))
            child.record_exception(base_exception)

        yield child


async def generate_trace_link_state() -> str:
    link_id: str = generate(size=30)
    data = {}
    constants.OTEL_PROPAGATOR.inject(data)
    await constants.REDIS_CLIENT.set(
        f"trace_context:{link_id}", orjson.dumps(data), ex=timedelta(days=1)
    )
    return link_id


async def get_context_from_link_state(link_id: str) -> Context | None:
    raw_data = await constants.REDIS_CLIENT.get(f"trace_context:{link_id}")
    if raw_data is None:
        return None

    data = orjson.loads(raw_data)
    return constants.OTEL_PROPAGATOR.extract(data)
