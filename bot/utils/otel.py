from contextlib import contextmanager
from typing import Literal

from opentelemetry.trace import Status, StatusCode

from bot.constants import OTEL_TRACER
from bot.exceptions import MessageTooLong, MissingQueueChannel

IGNORABLE_EXCEPTION_TYPES: tuple[type[Exception], ...] = (MessageTooLong, MissingQueueChannel)


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
