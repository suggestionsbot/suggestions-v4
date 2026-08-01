from IPython.utils.decorators import F
from curses import raw
import asyncio

import orjson
from commons import timing
from piccolo.columns.operators.comparison import GreaterThan, GreaterEqualThan, LessThan
import datetime
from collections import defaultdict
from typing import cast

import arrow
from piccolo.columns import Where, And
from piccolo.table import Table
from pydantic import BaseModel
from saq.types import Context

from bot.tables import CommandInvokes, AggregateCommandInvokes
from shared.utils import query_helpers


type COMMAND_NAME = str
type USER_LOCALE = str
type GUILD_LOCALE = str
type COMMAND_TYPE = str
type COUNT = int
type USER_ID = int
type GUILD_ID = int
type INVOKED_AT = datetime.datetime


class RawComputedData(BaseModel):
    """The base data to store alongside computed stats."""

    data_for_week_starting: datetime.datetime
    actions: dict[COMMAND_NAME, COUNT] = defaultdict(lambda: 0)
    action_types: dict[COMMAND_TYPE, COUNT] = defaultdict(lambda: 0)
    user_locales: dict[USER_LOCALE, COUNT] = defaultdict(lambda: 0)
    guild_locales: dict[GUILD_LOCALE, COUNT] = defaultdict(lambda: 0)
    user_usage_counters: dict[USER_ID, list[INVOKED_AT]] = defaultdict(list)
    guild_usage_counters: dict[GUILD_ID, list[INVOKED_AT]] = defaultdict(list)
    actions_invoked_by: dict[COMMAND_NAME, dict[USER_ID, list[INVOKED_AT]]] = defaultdict(
        lambda: defaultdict(list)
    )
    action_types_invoked_by: dict[COMMAND_TYPE, dict[USER_ID, list[INVOKED_AT]]] = (
        defaultdict(lambda: defaultdict(list))
    )


async def compute_base_data_for_week(
    ctx: Context, week_starting: arrow.Arrow
) -> RawComputedData:
    raw_data = RawComputedData(data_for_week_starting=week_starting.datetime)
    where_classes = And(
        Where(
            CommandInvokes.created_at, week_starting.datetime, operator=GreaterEqualThan
        ),
        Where(
            CommandInvokes.created_at,
            week_starting.shift(weeks=1).datetime,
            operator=LessThan,
        ),
    )
    await ctx["job"].update()
    async for row in query_helpers.iterate_over_table(
        CommandInvokes, where_clause=where_classes
    ):
        raw_data.actions[cast("COMMAND_NAME", row.action)] += 1
        raw_data.action_types[cast("COMMAND_TYPE", row.action_type)] += 1
        raw_data.user_locales[cast("USER_LOCALE", row.user_locale)] += 1
        if row.guild_locale is not None:
            raw_data.guild_locales[cast("GUILD_LOCALE", row.guild_locale)] += 1
            raw_data.user_usage_counters[cast("USER_ID", row.user_id)].append(
                cast(
                    "INVOKED_AT",
                    row.created_at,
                )
            )
        if row.guild_id is not None:
            raw_data.guild_usage_counters[cast("GUILD_ID", row.guild_id)].append(
                cast(
                    "INVOKED_AT",
                    row.created_at,
                )
            )
        raw_data.actions_invoked_by[cast("COMMAND_NAME", row.action)][
            cast("USER_ID", row.user_id)
        ].append(
            cast(
                "INVOKED_AT",
                row.created_at,
            )
        )
        raw_data.action_types_invoked_by[cast("COMMAND_TYPE", row.action_type)][
            cast("USER_ID", row.user_id)
        ].append(
            cast(
                "INVOKED_AT",
                row.created_at,
            )
        )
        await ctx["job"].update()

    return raw_data


class WeeklyAggregateData(BaseModel):
    total_users_seen: int = 0
    total_guilds_seen: int = 0
    total_voters_seen: int = 0
    total_users_who_only_voted: int = 0
    actions: dict[COMMAND_NAME, COUNT] = defaultdict(lambda: 0)
    action_types: dict[COMMAND_TYPE, COUNT] = defaultdict(lambda: 0)
    user_locales: dict[USER_LOCALE, COUNT] = defaultdict(lambda: 0)
    guild_locales: dict[GUILD_LOCALE, COUNT] = defaultdict(lambda: 0)
    raw_data: RawComputedData
    data_for_week_starting: datetime.datetime


async def calculate_weekly_aggregate(
    ctx: Context, raw_data: RawComputedData
) -> WeeklyAggregateData:
    await ctx["job"].update()
    data = WeeklyAggregateData(
        raw_data=raw_data, data_for_week_starting=raw_data.data_for_week_starting
    )
    data.total_users_seen = len(raw_data.user_usage_counters.keys())
    data.total_guilds_seen = len(raw_data.guild_usage_counters.keys())
    data.user_locales = raw_data.user_locales
    data.guild_locales = raw_data.guild_locales
    data.actions = raw_data.actions
    data.action_types = raw_data.action_types

    users_seen_voting = set(
        raw_data.actions_invoked_by[cast("COMMAND_NAME", "Suggestion Vote")].keys()
    )
    users_seen_running_commands: set = set()
    for k, v in raw_data.actions_invoked_by.items():
        if k == "Suggestion Vote":
            continue
        users_seen_running_commands.update(v)

    data.total_voters_seen = len(users_seen_voting)
    data.total_users_who_only_voted = len(
        users_seen_voting.difference(users_seen_running_commands)
    )

    return data


def stringify_keys(data: dict) -> dict:
    """Make compliant JSON."""
    return orjson.loads(orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS))


async def compute_aggregate_command_invokes(
    ctx: Context, *, force_load_short_week: bool = False
) -> None:
    min_datetime_str = await CommandInvokes.raw(
        "SELECT MIN(created_at) FROM command_invokes"
    )
    max_datetime_str = await CommandInvokes.raw(
        "SELECT MAX(created_at) FROM command_invokes"
    )
    if min_datetime_str[0]["min"] is None:
        # No command data yet
        return

    min_week = arrow.get(min_datetime_str[0]["min"])
    max_week = arrow.get(max_datetime_str[0]["max"])

    week_already_done_str = await CommandInvokes.raw(
        "SELECT MAX(data_for_week_starting) FROM aggregate_command_invokes"
    )
    if week_already_done_str and week_already_done_str[0]["max"] is not None:
        current_week = arrow.get(week_already_done_str[0]["max"]).shift(weeks=1)

        # If less then a week of data left to compute we
        # finish up and wait until we have an actual weeks worth
        if (
            timing.is_within_next_(
                current_week.datetime,
                max_week.datetime,
                datetime.timedelta(weeks=1),
            )
            and not force_load_short_week
        ):
            return

    else:
        # If no aggregate data, start from start
        current_week = min_week

    raw_data_rows: list[RawComputedData] = []
    while not timing.is_in_the_past(current_week.datetime, max_week.datetime):
        raw_data_rows.append(await compute_base_data_for_week(ctx, current_week))
        current_week = current_week.shift(weeks=1)

        # If less then a week of data left to compute we
        # finish up and wait until we have an actual weeks worth
        if (
            timing.is_within_next_(
                current_week.datetime,
                max_week.datetime,
                datetime.timedelta(weeks=1),
            )
            and not force_load_short_week
        ):
            break

    aggregate_rows: list[WeeklyAggregateData] = [
        await calculate_weekly_aggregate(ctx, raw_data) for raw_data in raw_data_rows
    ]
    for row in aggregate_rows:
        db_row = AggregateCommandInvokes(
            total_users_seen=row.total_users_seen,
            total_guilds_seen=row.total_guilds_seen,
            total_voters_seen=row.total_voters_seen,
            total_users_who_only_voted=row.total_users_who_only_voted,
            actions=stringify_keys(row.actions),
            action_types=stringify_keys(row.action_types),
            user_locales=stringify_keys(row.user_locales),
            guild_locales=stringify_keys(row.guild_locales),
            raw_data=stringify_keys(row.raw_data.model_dump()),
            data_for_week_starting=row.data_for_week_starting,
        )
        await db_row.save()


if __name__ == "__main__":
    from unittest.mock import AsyncMock

    mock_ctx = {"job": AsyncMock()}

    asyncio.run(compute_aggregate_command_invokes(mock_ctx, force_load_short_week=True))
