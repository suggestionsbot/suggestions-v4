from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from litestar import Request
from litestar.connection import ASGIConnection
from litestar.plugins.flash import flash

from web.util.table_mixins import utc_now

if TYPE_CHECKING:
    from web.tables import Users


def alert(
    request: Request | ASGIConnection,
    message: str,
    level: Literal["info", "warning", "error", "success"] = "info",
):
    """A helper function given we hard code level in templates"""
    flash(request, message, category=level)


async def inject_alerts(request: Request | ASGIConnection, user: Users):
    """Ensure lazy alerts make it through to the user"""
    if (
        hasattr(request, "route_handler")
        and "is_api_route" in request.route_handler.opt
        and request.route_handler.opt["is_api_route"] is True
    ):
        # Don't show alerts on api routes
        return

    from web.tables import Alerts

    # noinspection PyTypeChecker
    alerts_to_show: list[Alerts] = await Alerts.objects().where(  # type: ignore
        Alerts.target == user,  # type: ignore
    )
    for alert_obj in alerts_to_show:
        alert(request, alert_obj.message, alert_obj.level)
        alert_obj.has_been_shown = True
        alert_obj.was_shown_at = utc_now()
        await alert_obj.save()
