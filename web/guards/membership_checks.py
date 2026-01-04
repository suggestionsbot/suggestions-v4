from litestar import Request
from litestar.connection import ASGIConnection
from litestar.datastructures import State
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.handlers import BaseRouteHandler

from web.controllers.oauth_controller import DISCORD_OAUTH
from web.exception_handlers import RedirectForAuth
from web.tables import Users, OAuthEntry
from web.util import alert


async def ensure_user_is_in_guild(
    request: Request[Users, None, State], route_handler: BaseRouteHandler
):
    if not request.user or request.user is None:
        return RedirectForAuth(str(request.url))

    guild_id = request.path_params.get("guild_id")
    oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
    user_is_in_guild = await DISCORD_OAUTH.is_user_in_guild(
        oauth_entry.access_token,
        user_id=oauth_entry.oauth_id,
        guild_id=guild_id,
    )
    if not user_is_in_guild:
        if request.user.admin:
            alert(
                request,
                "I am only letting you into this page because you are dashboard admin.",
                level="info",
            )
            return None

        alert(request, "You must be in the guild to view it.", level="error")
        raise PermissionDeniedException

    return None
