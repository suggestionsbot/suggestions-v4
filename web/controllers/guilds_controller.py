from litestar import Controller, get, Request
from litestar.response import Template

from web.controllers.oauth_controller import DISCORD_OAUTH
from web.middleware import EnsureAdmin, EnsureAuth
from web.tables import OAuthEntry
from web.util import html_template


class GuildController(Controller):
    middleware = [EnsureAuth]
    include_in_schema = False
    path = "/guilds"

    @get(path="/", name="view_guilds")
    async def view_guilds(self, request: Request) -> Template:
        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        guilds = await DISCORD_OAUTH.get_user_guilds(oauth_entry.access_token)
        return html_template(
            "guilds/view_guilds.jinja",
            {"guilds": guilds},
            csp_allow_discord_cdn_in_images=True,
        )
