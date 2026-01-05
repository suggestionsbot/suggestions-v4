from urllib.parse import unquote_plus

from litestar import Controller, get, Request
from litestar.response import Template, Redirect

from shared.tables import GuildConfigs, Suggestions, QueuedSuggestions
from shared.utils import configs
from web import constants
from web.controllers.oauth_controller import DISCORD_OAUTH
from web.guards import ensure_user_is_in_guild, ensure_user_has_manage_permissions
from web.middleware import EnsureAdmin, EnsureAuth
from web.tables import OAuthEntry
from web.util import html_template, alert


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

    @get(
        path="/{guild_id:int}/generate_invite",
        name="generate_guild_invite",
        guards=[ensure_user_is_in_guild],
    )
    async def generate_guild_invite(self, guild_id: int) -> Redirect:
        # Exists so we can clear to guild cache
        await DISCORD_OAUTH.set_tmp_bot_joining_guild(guild_id)
        return Redirect(
            f"{constants.BOT_INVITE_URL}&guild_id={guild_id}",
            status_code=302,
        )

    @get(
        path="/{guild_id:int}/{guild_name:str}/onboarding",
        name="guild_onboarding",
        guards=[ensure_user_has_manage_permissions],
    )
    async def guild_onboarding(
        self, request: Request, guild_id: int, guild_name: str
    ) -> Redirect:
        alert(request, "Onboarding page doesnt exist yet", level="warning")
        return Redirect(
            request.url_for(
                "view_guild", guild_id=str(guild_id), guild_name=guild_name
            ),
            status_code=302,
        )

    @get(
        path="/{guild_id:int}/{guild_name:str}/settings",
        name="guild_settings",
        guards=[ensure_user_has_manage_permissions],
    )
    async def guild_settings(
        self, request: Request, guild_id: int, guild_name: str
    ) -> Redirect:
        alert(request, "Settings page doesnt exist yet", level="warning")
        return Redirect(
            request.url_for(
                "view_guild", guild_id=str(guild_id), guild_name=guild_name
            ),
            status_code=302,
        )

    @get(
        path="/{guild_id:str}/{guild_name:str}",
        name="view_guild",
        guards=[ensure_user_is_in_guild],
    )
    async def view_guild(
        self, request: Request, guild_id: int, guild_name: str
    ) -> Template:
        guild_name = unquote_plus(guild_name)
        if constants.IS_PRODUCTION:  # Save time locally
            is_bot_in_guild = await DISCORD_OAUTH.is_bot_in_guild(guild_id)
            if not is_bot_in_guild:
                return html_template(
                    "guilds/not_in_guild.jinja",
                    context={
                        "guild_name": guild_name,
                        "guild_id": guild_id,
                    },
                )

        oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
        profile = await DISCORD_OAUTH.get_profile(
            oauth_entry.access_token, oauth_entry.oauth_id
        )
        guild_config: GuildConfigs = await configs.ensure_guild_config(guild_id)
        requires_config = guild_config.suggestions_channel_id is None
        requires_config = False
        total_suggestions = await Suggestions.count().where(
            Suggestions.guild_configuration.guild_id == guild_id
        )
        suggestions_in_queue = await QueuedSuggestions.count().where(
            QueuedSuggestions.guild_configuration.guild_id == guild_id
        )
        total_suggestions = "Currently Unavailable"

        return html_template(
            "guilds/view_guild.jinja",
            context={
                "user_name": profile["global_name"],
                "guild_name": guild_name,
                "guild_id": guild_id,
                "requires_config": requires_config,
                "total_suggestions": total_suggestions,
                "suggestions_in_queue": suggestions_in_queue,
            },
        )
