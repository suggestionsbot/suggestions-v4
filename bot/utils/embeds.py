from __future__ import annotations

import logging
import typing

import hikari

from bot.constants import ErrorCode, ERROR_COLOR
from shared.tables.mixins.audit import utc_now

if typing.TYPE_CHECKING:
    from bot.tables import InternalErrors

logger = logging.getLogger(__name__)


def error_embed(
    title: str,
    description: str,
    *,
    internal_error_reference: InternalErrors | None = None,
    footer_text: str | None = None,
    error_code: ErrorCode | None = None,
) -> hikari.Embed:
    # TODO Also show a button to self diagnose with a link for more info maybe?
    embed = hikari.Embed(
        title=title,
        description=description,
        color=ERROR_COLOR,
        timestamp=utc_now(),
    )
    if footer_text and error_code:
        raise ValueError("Can't provide both footer_text and error_code")

    elif footer_text:
        embed.set_footer(text=footer_text)

    elif error_code:
        if internal_error_reference:
            embed.set_footer(
                text=f"Error code {error_code.value} | Error ID {internal_error_reference.id}"
            )
        else:
            embed.set_footer(text=f"Error code {error_code.value}")

        logger.debug("Encountered %s", error_code.name)

    elif internal_error_reference:
        embed.set_footer(text=f"Error ID {internal_error_reference.id}")

    return embed
