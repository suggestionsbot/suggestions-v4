from __future__ import annotations

import traceback

from piccolo.columns import Text, Varchar, BigInt, Boolean
from piccolo.table import Table

from shared.tables.mixins import AuditMixin
from bot.utils import generate_id


class InternalErrors(AuditMixin, Table):
    # Old is 8 chars, new is 11
    id = Varchar(
        length=11,
        default=generate_id,
        help_text="The ID of this error",
        primary_key=True,
        unique=True,
        index=True,
    )
    traceback = Text(help_text="The full error traceback")
    error_name = Text(help_text="The class name of the error")
    user_id = BigInt(
        help_text="The user who triggered the error", null=True, default=None
    )
    guild_id = BigInt(
        help_text="The guild where the error was triggered", null=True, default=None
    )
    command_name = Varchar(
        default=None,
        null=True,
        length=100,
        help_text="The name of the command in which the error was triggered",
    )
    has_been_fixed = Boolean(
        default=False,
        help_text="Has this specific error been fixed? "
        "'This' being hash((self.error_name, self.traceback, self.command_name))",
    )
    trace_id = Text(
        help_text="The OTEL trace id if applicable associated with this error",
        default=None,
        null=True,
    )
    extra_info = Text(
        help_text="Extra info added to this error",
        default=None,
        null=True,
    )

    def __hash__(self) -> int:
        # Error objects should 'unique' based off the error itself
        # and not the extra metadata such as cluster or shard of execution
        return hash((self.error_name, self.traceback, self.command_name))

    @classmethod
    async def persist_error(
        cls,
        exception: Exception | str,
        *,
        command_name: str,
        user_id: int | None = None,
        guild_id: int | None = None,
        extra_info: str | None = None,
    ) -> InternalErrors:
        from bot.utils import get_trace_id

        traceback_for_col = (
            exception
            if isinstance(exception, str)
            else "".join(traceback.format_exception(exception))
        )
        otel_ctx = get_trace_id()
        if otel_ctx == "00000000000000000000000000000000":
            # Sometimes it dont got a trace??
            otel_ctx = None

        internal_error = cls(
            id=generate_id(),
            traceback=traceback_for_col,
            error_name=exception.__class__.__name__,
            command_name=command_name,
            guild_id=guild_id,
            user_id=user_id,
            trace_id=otel_ctx or None,
            extra_info=extra_info,
        )
        await internal_error.save()
        return internal_error

    @property
    def url(self) -> str:
        """Return a URL to view in the dashboard."""
        return f"https://dashboard.suggestions.gg/errors/{self.id}"

    @property
    def otel_url(self) -> str:
        """Return a URL to view this trace in the signoz dashboard."""
        return f"https://signals.oof.nz/trace/{self.trace_id}"
