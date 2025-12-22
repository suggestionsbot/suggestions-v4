from litestar import Controller, get, Request
from litestar.response import Template

from web.controllers.oauth_controller import DISCORD_OAUTH
from web.middleware import EnsureAdmin
from web.tables import OAuthEntry
from web.util import html_template


class DebugController(Controller):
    middleware = [EnsureAdmin]
    include_in_schema = False
    path = "/debug"

    @get(path="/oauth/data", name="debug_oauth_data")
    async def list_oauth(self, request: Request) -> Template:
        """List all oauth raw data"""
        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        profile = await DISCORD_OAUTH.get_profile(oauth_entry.access_token)
        guilds = await DISCORD_OAUTH.get_user_guilds(oauth_entry.access_token)
        return html_template(
            "debug/oauth_data.jinja",
            {
                "title": "OAuth Data",
                "profile": profile,
                "guilds": guilds,
            },
        )
