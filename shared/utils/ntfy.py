from typing import Literal
from bot.tables import InternalErrors
import logging

import httpx

from web.constants import NTFY_API_KEY, NTFY_URL, NTFY_TOPIC

log = logging.getLogger(__name__)


async def notify_ethan_of_something(
    *,
    title: str,
    message: str,
    priority: Literal[1, 2, 3, 4, 5] = 3,
    tags: str | None = None,
    internal_error_reference: InternalErrors | None = None,
) -> None:
    """Send notifications to Ethan for review.

    Parameters
    ----------
    title: str
        The notification title.
    message: str
        The message body as markdown
    priority : Literal[1, 2, 3, 4, 5]
        The priority of the notification.

        Defaults to three. Five is max, one is min.
    tags: str | None
        The tags as a comma separated list of tags.

        Good example is 'warning' or 'rotating_light'
    internal_error_reference: InternalErrors | None
        If present, adds a link to view the error in the dashboard.

    """
    actions = []
    if internal_error_reference is not None:
        actions.append(
            {
                "action": "view",
                "label": "Error in context",
                "url": internal_error_reference.url,
            }
        )

    headers = {
        "Authorization": f"Bearer {NTFY_API_KEY}",
        "Markdown": "yes",
        "Priority": str(priority),
    }
    if tags is not None:
        headers["Tags"] = tags

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            NTFY_URL,
            headers=headers,
            json={
                "topic": NTFY_TOPIC,
                "Title": title,
                "message": message,
                "actions": actions,
            },
        )
        # If this hasnt worked, dont error
        if resp.status_code != 200:  # noqa: PLR2004
            log.error("Cannot reach ntfy, received code %s", resp.status_code)
