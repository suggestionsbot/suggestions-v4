import datetime

import httpx
from litestar import Controller, get, Request
from litestar.response import Template

from web import constants
from web.controllers.oauth_controller import DISCORD_OAUTH
from web.middleware import EnsureAdmin
from web.tables import OAuthEntry
from web.util import html_template, signoz_querying


class DebugController(Controller):
    middleware = [EnsureAdmin]
    include_in_schema = False
    path = "/debug"

    @get(path="/oauth/data", name="debug_oauth_data")
    async def list_oauth(self, request: Request) -> Template:
        """List all oauth raw data"""
        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        profile = await DISCORD_OAUTH.get_profile(
            oauth_entry.access_token, oauth_entry.oauth_id
        )
        cache_key = f"OAUTH:GUILDS:{oauth_entry.oauth_id}"
        guild_cache_hit = await constants.REDIS_CLIENT.exists(cache_key)
        guilds = await DISCORD_OAUTH.get_user_guilds(
            oauth_entry.access_token, user_id=oauth_entry.oauth_id
        )
        return html_template(
            "debug/oauth_data.jinja",
            {
                "title": "OAuth Data",
                "profile": profile,
                "guilds": guilds,
                "guild_cache_hit": guild_cache_hit,
            },
        )

    @get(path="/signoz/data", name="debug_signoz_data")
    async def list_signoz(self, request: Request) -> Template:
        """List all signoz query data"""
        timescale: datetime.timedelta = datetime.timedelta(days=-1)
        # TODO Expose this functionality via the file itself and also wrap in redis cache
        async with httpx.AsyncClient(
            headers=signoz_querying.HEADERS, base_url=signoz_querying.BASE_URL
        ) as client:
            users_resp = await client.post(
                "/v5/query_range",
                json=signoz_querying.build_trace_query(
                    signoz_querying.UNIQUE_GLOBAL_USERS_QUERY, timescale
                ),
            )
            users = users_resp.json()["data"]["data"]["results"][0]["data"][0][0]
            guilds_resp = await client.post(
                "/v5/query_range",
                json=signoz_querying.build_trace_query(
                    signoz_querying.UNIQUE_GLOBAL_GUILDS_QUERY, timescale
                ),
            )
            guilds = guilds_resp.json()["data"]["data"]["results"][0]["data"][0][0]

        return html_template(
            "debug/signoz_data.jinja",
            {"users": users, "timescale": timescale, "guilds": guilds},
        )
