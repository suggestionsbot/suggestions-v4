from __future__ import annotations

import traceback

from piccolo.columns import Text, Varchar, BigInt, Integer, Boolean
from piccolo.table import Table

from bot.tables.mixins import AuditMixin
from bot.utils import generate_id


class InternalError(AuditMixin, Table):
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
    user_id = BigInt(help_text="The user who triggered the error")
    guild_id = BigInt(help_text="The guild where the error was triggered")
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

    def __hash__(self):
        # Error objects should 'unique' based off the error itself
        # and not the extra metadata such as cluster or shard of execution
        return hash((self.error_name, self.traceback, self.command_name))

    @classmethod
    async def persist_error(
        cls,
        exception: Exception,
        *,
        command_name: str,
        guild_id: int,
        author_id: int,
    ) -> InternalError:
        internal_error = cls(
            id=generate_id(),
            traceback="".join(traceback.format_exception(exception)),
            error_name=exception.__class__.__name__,
            command_name=command_name,
            guild_id=guild_id,
            user_id=author_id,
        )
        await internal_error.save()
        return internal_error
