from __future__ import annotations
import asyncio

from collections.abc import AsyncGenerator
from typing import cast, TypeVar, Protocol

from piccolo.columns import ForeignKey, Serial
from piccolo.custom_types import TableInstance, Combinable
from piccolo.query import Query, Objects
from piccolo.querystring import QueryString

DEFAULT_PAGE_SIZE = 500


class SuggestionsTableInstance(Protocol):
    id: Serial

    @classmethod
    def objects(
        cls, *prefetch: ForeignKey | list[ForeignKey]
    ) -> Objects[TableInstance]: ...


T = TypeVar("T")


async def build_base_cursor_query(
    *,
    table_class: SuggestionsTableInstance,
    prefetch_cols: list[ForeignKey] | None = None,
    order_by: Serial,
    cursor_col: Serial,
    next_cursor_id: int | None,
    where_clause: Combinable | QueryString | None = None,
) -> Query:
    if prefetch_cols is None:
        prefetch_cols = []

    base_query = (
        table_class.objects(*prefetch_cols)
        .limit(DEFAULT_PAGE_SIZE + 1)
        .order_by(order_by)
    )
    if next_cursor_id is not None:
        base_query = base_query.where(cursor_col >= next_cursor_id)

    if where_clause is not None:
        base_query = base_query.where(where_clause)

    return base_query


async def iterate_over_table[T: SuggestionsTableInstance](
    table_class: T,
    prefetch_cols: list[ForeignKey] | None = None,
    where_clause: Combinable | QueryString | None = None,
) -> AsyncGenerator[T]:
    """Cursor based pagination helper."""
    next_cursor: int | None = None
    has_next_queued: bool = True
    while has_next_queued:
        query: Query = await build_base_cursor_query(
            table_class=table_class,
            prefetch_cols=prefetch_cols,
            order_by=cast("Serial", cast("object", table_class.id)),
            cursor_col=cast("Serial", cast("object", table_class.id)),
            next_cursor_id=next_cursor,
            where_clause=where_clause,
        )

        rows: list[SuggestionsTableInstance] = await query.run()
        next_cursor = None
        if len(rows) > DEFAULT_PAGE_SIZE:
            final_row = rows.pop(-1)
            next_cursor = final_row.id
        else:
            has_next_queued = False

        for row in rows:
            yield row  # ty:ignore[invalid-yield]

        # This may be long-running so do a little giving back
        await asyncio.sleep(0)
