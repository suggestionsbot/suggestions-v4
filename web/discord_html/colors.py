"""Suggestions bot palette, mirrored from the bot's constants.

The bot sets these as the container ``accent_color``, so rendered messages pick
them up automatically. They're exposed here (and as CSS variables) so the rest
of a page — status badges, filters, headings — can use the same colours.
"""

from __future__ import annotations

ERROR_COLOR = 0xD63031        # (214, 48, 49)
REJECTED_COLOR = 0xCF000F     # (207, 0, 15)
APPROVED_COLOR = 0x00E640     # (0, 230, 64)
IMPLEMENTED_COLOR = 0x85DEFF  # (133, 222, 255)
DUPLICATE_COLOR = 0xC859FF    # (200, 89, 255)
PENDING_COLOR = 0xFFD663      # (255, 214, 99)
EMBED_COLOR = 0xFFD663        # (255, 214, 99)

STATE_COLORS: dict[str, int] = {
    "pending": PENDING_COLOR,
    "approved": APPROVED_COLOR,
    "rejected": REJECTED_COLOR,
    "implemented": IMPLEMENTED_COLOR,
    "duplicate": DUPLICATE_COLOR,
    "error": ERROR_COLOR,
    "embed": EMBED_COLOR,
}


def state_color(state: object) -> int:
    """Colour for a suggestion state: an enum (``SuggestionStateEnum.APPROVED``),
    its value, or a name, case-insensitive. Unknown states get ``EMBED_COLOR``."""
    key = getattr(state, "value", state)
    return STATE_COLORS.get(str(key).strip().lower(), EMBED_COLOR)
