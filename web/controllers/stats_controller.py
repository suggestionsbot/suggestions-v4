from collections import defaultdict

import orjson
from bot.tables import AggregateCommandInvokes
from litestar import Controller, get, Request
from litestar.response import Template, Redirect

from web.middleware import EnsureAdmin
from web.util import html_template, alert


def update_collection_with_row(collection: dict, data: str) -> None:
    actions_loaded = orjson.loads(data)
    for k, v in actions_loaded.items():
        collection[k] = v


def sort_dict_by_value(data: dict) -> dict:
    return dict(
        sorted(
            data.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


class StatsController(Controller):
    middleware = [EnsureAdmin]  # noqa: RUF012
    include_in_schema = False
    path = "/stats"

    @get(path="/aggregate", name="view_invoke_stats")
    async def view_stats(
        self, request: Request, weeks: int = 4, offset: int = 0
    ) -> Template | Redirect:
        all_aggregate_stats = (
            await AggregateCommandInvokes.objects()
            .order_by(AggregateCommandInvokes.data_for_week_starting, ascending=False)
            .limit(weeks)
            .offset(offset)
        )
        all_aggregate_stats = sorted(
            all_aggregate_stats, key=lambda x: x.data_for_week_starting
        )
        total_users_seen: int = 0
        total_guilds_seen: int = 0
        total_voters_seen: int = 0
        total_users_who_only_voted: int = 0
        actions = defaultdict(lambda: 0)
        action_types = defaultdict(lambda: 0)
        user_locales = defaultdict(lambda: 0)
        guild_locales = defaultdict(lambda: 0)
        for row in all_aggregate_stats:
            total_users_seen += row.total_users_seen
            total_guilds_seen += row.total_guilds_seen
            total_voters_seen += row.total_voters_seen
            total_users_who_only_voted += row.total_users_who_only_voted
            update_collection_with_row(actions, row.actions)
            update_collection_with_row(action_types, row.action_types)
            update_collection_with_row(user_locales, row.user_locales)
            update_collection_with_row(guild_locales, row.guild_locales)

        actions = sort_dict_by_value(actions)
        return html_template(
            "stats/aggregate.jinja",
            context={
                "all_aggregate_stats": all_aggregate_stats,
                "earliest": all_aggregate_stats[0].data_for_week_starting,
                "latest": all_aggregate_stats[-1].data_for_week_starting,
                "weeks": weeks,
                "offset": offset,
                "actions": actions,
                "action_types": action_types,
                "user_locales": user_locales,
                "guild_locales": guild_locales,
                "total_users_seen": total_users_seen,
                "total_guilds_seen": total_guilds_seen,
                "total_voters_seen": total_voters_seen,
                "total_users_who_only_voted": total_users_who_only_voted,
            },
        )
