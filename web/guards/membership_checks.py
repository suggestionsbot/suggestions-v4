from typing import cast

import hikari
from litestar import Request
from litestar.connection import ASGIConnection
from litestar.datastructures import State
from litestar.exceptions import PermissionDeniedException
from litestar.handlers import BaseRouteHandler

from web.controllers.oauth_controller import DISCORD_OAUTH
from web.exception_handlers import RedirectForAuth
from web.tables import Users, OAuthEntry
from web.util import alert


async def ensure_user_is_in_guild(request: ASGIConnection, route_handler: BaseRouteHandler) -> None:
    request = cast(Request[Users, None, State], request)
    if not request.user or request.user is None:
        raise RedirectForAuth(str(request.url))

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


async def ensure_user_has_manage_permissions(
    request: ASGIConnection, route_handler: BaseRouteHandler
) -> None:
    """Lets the following users through:
    - Dashboard admin
    - Server owner
    - Admin perms
    - Manage server perms
    """
    request = cast(Request[Users, None, State], request)
    if not request.user or request.user is None:
        raise RedirectForAuth(str(request.url))

    guild_id = request.path_params.get("guild_id")
    if request.user.admin:
        alert(
            request,
            "As a dashboard admin I am letting you in",
            level="info",
        )
        return None

    oauth_entry: OAuthEntry = await request.user.get_oauth_entry()
    guild_data = await DISCORD_OAUTH.get_user_data_in_guild(
        oauth_entry.access_token,
        user_id=oauth_entry.oauth_id,
        guild_id=guild_id,
    )
    if guild_data is None:
        alert(
            request,
            "You must be in the guild with sufficient permissions.",
            level="error",
        )
        raise PermissionDeniedException

    if guild_data["owner"] is True:
        return None

    perms = hikari.Permissions(guild_data["permissions"])
    if ((perms & hikari.Permissions.MANAGE_GUILD) == hikari.Permissions.MANAGE_GUILD) or (
        (perms & hikari.Permissions.ADMINISTRATOR) == hikari.Permissions.ADMINISTRATOR
    ):
        return None

    alert(
        request,
        "You must have MANAGE_GUILD or ADMINISTRATOR permissions to view this page.",
        level="error",
    )
    raise PermissionDeniedException
