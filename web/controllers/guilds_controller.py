from urllib.parse import unquote_plus

from litestar import Controller, get, Request
from litestar.response import Template, Redirect

from web import constants
from web.controllers.oauth_controller import DISCORD_OAUTH
from web.middleware import EnsureAdmin, EnsureAuth
from web.tables import OAuthEntry
from web.util import html_template


class GuildController(Controller):
    middleware = [EnsureAuth]
    include_in_schema = False
    path = "/guilds"

    @get(path="/", name="view_all_guilds")
    async def view_all_guilds(self, request: Request) -> Template:
        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        guilds = await DISCORD_OAUTH.get_user_guilds(
            oauth_entry.access_token, user_id=oauth_entry.oauth_id
        )
        return html_template(
            "guilds/view_all_guilds.jinja",
            {"guilds": guilds},
            csp_allow_discord_cdn_in_images=True,
        )

    @get(path="/guilds/{guild_id:int}/generate_invite", name="generate_guild_invite")
    async def generate_guild_invite(self, guild_id: int) -> Redirect:
        # Exists so we can clear to guild cache
        await DISCORD_OAUTH.set_tmp_bot_joining_guild(guild_id)
        return Redirect(
            f"{constants.BOT_INVITE_URL}&guild_id={guild_id}",
            status_code=302,
        )

    @get(path="/{guild_id:str}/{guild_name:str}", name="view_guild")
    async def view_guild(
        self, request: Request, guild_id: int, guild_name: str
    ) -> Template:
        guild_name = unquote_plus(guild_name)
        is_bot_in_guild = await DISCORD_OAUTH.is_bot_in_guild(guild_id)
        if not is_bot_in_guild:
            return html_template(
                "guilds/not_in_guild.jinja",
                context={
                    "guild_name": guild_name,
                    "guild_id": guild_id,
                },
            )
