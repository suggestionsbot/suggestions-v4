"""Render Discord Components V2 messages (e.g. Hikari builders) as HTML with Jinja.

Usage::

    import jinja2
    import discord_html

    env = jinja2.Environment(loader=..., autoescape=True)
    discord_html.setup_jinja(env)

    # in a route / view
    components = await suggestion.as_components(...)   # Hikari builders
    html = env.get_template("suggestion.html").render(
        components=components,
        discord_ctx=discord_html.DiscordContext(users={author_id: "Skelmis"}),
    )

and in the template::

    {% import "discord/components.html.j2" as discord with context %}
    {{ discord_styles() }}
    {{ discord.message(components) }}
    {{ discord_scripts() }}
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import jinja2
from markupsafe import Markup

import datetime as dt

from . import colors
from .colors import STATE_COLORS, state_color
from .markdown import (
    TWEMOJI_BASE,
    DiscordContext,
    color_rule,
    format_timestamp,
    render_markdown,
    timestamp_html,
    twemoji_img,
)

__all__ = [
    "DiscordContext",
    "STATE_COLORS",
    "TEMPLATE_DIR",
    "TWEMOJI_BASE",
    "STATIC_DIR",
    "format_timestamp",
    "render_markdown",
    "safe_url",
    "setup_jinja",
    "state_color",
    "to_payload",
]

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

_SAFE_SCHEMES = {"http", "https"}


def to_payload(components: Any) -> list[dict]:
    """Normalise Hikari builders, raw dicts, or a mix into Discord payload dicts.

    Hikari's ``ComponentBuilder.build()`` returns ``(payload, attachments)`` in
    current versions and a bare mapping in some older ones; both are handled.
    """
    if components is None:
        return []
    if inspect.isawaitable(components):
        if inspect.iscoroutine(components):
            components.close()  # avoid a "never awaited" warning on top of the error
        raise TypeError(
            "Got a coroutine, not components. Await it first: "
            "components = await suggestion.as_components(...)"
        )
    if isinstance(components, (str, bytes)):
        raise TypeError("Expected components, got a string")
    if isinstance(components, Mapping) or hasattr(components, "build"):
        components = [components]

    out: list[dict] = []
    for item in components:
        if isinstance(item, Mapping):
            out.append(dict(item))
        elif hasattr(item, "build"):
            built = item.build()
            out.append(dict(built[0] if isinstance(built, tuple) else built))
        else:
            raise TypeError(f"Cannot render component of type {type(item).__name__}")
    return out


def safe_url(url: Any, *, allow_paths: bool = False) -> str:
    """Return the URL if it is http(s) (or, with ``allow_paths``, a same-origin
    path like "/static/x.png"), otherwise an empty string.

    Media URLs and link buttons come from user input, so anything like
    ``javascript:`` must never reach an ``href`` or ``src``. Paths are only
    accepted from developer-supplied values (the media_url hook's output, the
    Twemoji base, the header avatar), never from message payloads: an <img>
    pointed at a same-origin path makes every viewer's browser send that GET
    request with their cookies (e.g. a sign-out URL).
    """
    if isinstance(url, Mapping):  # unfurled media objects: {"url": "..."}
        url = url.get("url")
    if not isinstance(url, str):
        return ""
    stripped = url.strip()
    if (
        allow_paths
        and stripped.startswith("/")
        and not stripped.startswith("//")
        and "\\" not in stripped
        and not any(ord(ch) < 0x20 for ch in stripped)
    ):
        return stripped  # same-origin path: fits a CSP of img-src 'self'
    try:
        scheme = urlsplit(url.strip()).scheme.lower()
    except ValueError:
        return ""
    return url.strip() if scheme in _SAFE_SCHEMES else ""


def hex_color(value: Any) -> str:
    """``0x5865F2`` → ``#5865f2``; accepts ints, Hikari Color, or None."""
    if value is None:
        return ""
    try:
        return f"#{int(value) & 0xFFFFFF:06x}"
    except (TypeError, ValueError):
        return ""


def _coerce_context(ctx: Any) -> DiscordContext | None:
    if isinstance(ctx, DiscordContext):
        return ctx
    if isinstance(ctx, Mapping):  # allow plain dicts: {"users": {...}, ...}
        return DiscordContext(**ctx)
    return None


def _twemoji_base(environment: jinja2.Environment) -> str | None:
    return (environment.globals.get("_discord_html") or {}).get("twemoji_base")


def _nonce(context: jinja2.runtime.Context) -> str | None:
    """The page's CSP nonce, taken from the ``csp_nonce`` template variable."""
    nonce = context.get("csp_nonce")
    return str(nonce) if nonce else None


def _nonce_attr(context: jinja2.runtime.Context) -> Markup:
    nonce = _nonce(context)
    return Markup(' nonce="{}"').format(nonce) if nonce else Markup("")


@jinja2.pass_context
def _markdown_filter(context: jinja2.runtime.Context, text: Any) -> Markup:
    return render_markdown(
        text,
        _coerce_context(context.get("discord_ctx")),
        twemoji_base=_twemoji_base(context.environment),
        nonce=_nonce(context),
    )


@jinja2.pass_context
def discord_color_rule(context: jinja2.runtime.Context, css_class: str, prop: str, color: str) -> Markup:
    """A nonce-carrying ``<style>`` that sets one colour on one class."""
    return Markup(color_rule(css_class, prop, color, _nonce(context)))


@jinja2.pass_environment
def _unicode_emoji_filter(environment: jinja2.Environment, name: Any) -> Markup:
    """A button/select emoji given by its Unicode name ("✅")."""
    name = str(name or "")
    base = _twemoji_base(environment)
    if base and name:
        return Markup(twemoji_img(name, base))
    return Markup('<span class="dc-emoji-unicode">{}</span>').format(name)


@jinja2.pass_context
def discord_timestamp(context: jinja2.runtime.Context, value: Any, style: str = "S") -> Markup:
    """``<time>`` for a datetime or unix timestamp (style as in ``<t:…:style>``,
    plus "S" for the short message-header format)."""
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.astimezone()
        value = value.timestamp()
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return Markup("")
    ctx = _coerce_context(context.get("discord_ctx"))
    return Markup(timestamp_html(ts, style, ctx.now if ctx else None) or "")


@functools.cache
def _read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


@jinja2.pass_context
def discord_styles(context: jinja2.runtime.Context) -> Markup:
    """Inline ``<style>`` block (carries ``csp_nonce`` if the page has one)."""
    return Markup("<style{}>").format(_nonce_attr(context)) + Markup(_read_static("discord-components.css")) + Markup("</style>")


@jinja2.pass_context
def discord_scripts(context: jinja2.runtime.Context) -> Markup:
    """Inline ``<script>`` that localises timestamps and handles spoilers
    (carries ``csp_nonce`` if the page has one)."""
    return Markup("<script{}>").format(_nonce_attr(context)) + Markup(_read_static("discord-components.js")) + Markup("</script>")


def setup_jinja(
    env: jinja2.Environment,
    *,
    media_url: Callable[[str], str | None] | None = None,
    twemoji: bool | str = False,
    videos: str = "player",
) -> jinja2.Environment:
    """Register the component templates, filters and globals on ``env``.

    Your existing loader keeps priority; the component templates are added as a
    fallback under ``discord/``. Safe to call more than once.

    ``media_url`` rewrites image/thumbnail/file URLs before they reach the page,
    e.g. to route user-supplied images through your own proxy so viewers' IPs
    aren't sent to arbitrary hosts, or to same-origin paths so they fit a CSP
    of ``img-src 'self'``. Return ``None``/``""`` for media the page can't load;
    it's then shown as a link instead of a broken image. Its return value is
    checked again, so it can't introduce unsafe URLs.

    ``videos``: ``"player"`` renders ``<video>``; ``"link"`` renders a card
    linking to the file, for pages whose CSP has no ``media-src`` (browsers
    don't honour nonces on media, so nothing else can make them play).

    ``twemoji`` renders Unicode emoji as Twemoji images like Discord does:
    ``True`` uses the jsDelivr CDN, or pass your own base URL (ending in "/")
    to self-host the SVGs.
    """
    if videos not in ("player", "link"):
        raise ValueError('videos must be "player" or "link"')
    if twemoji:
        base = TWEMOJI_BASE if twemoji is True else safe_url(str(twemoji), allow_paths=True)
        if not base:
            raise ValueError("twemoji must be True or an http(s) base URL")
        twemoji = base if base.endswith("/") else base + "/"
    if not getattr(env, "_discord_html_setup", False):
        ours = jinja2.FileSystemLoader(str(TEMPLATE_DIR))
        env.loader = jinja2.ChoiceLoader([env.loader, ours]) if env.loader else ours
        env._discord_html_setup = True  # type: ignore[attr-defined]

    def media_filter(value: Any) -> str:
        """Media from a message payload: must be absolute http(s)."""
        url = safe_url(value)
        if url and media_url:
            return safe_url(media_url(url) or "", allow_paths=True)
        return url

    def asset_filter(value: Any) -> str:
        """Developer-supplied image (e.g. the header avatar): paths allowed."""
        url = safe_url(value, allow_paths=True)
        if url and media_url and not url.startswith("/"):
            return safe_url(media_url(url) or "", allow_paths=True)
        return url

    env.filters.update(
        discord_markdown=_markdown_filter,
        discord_payload=to_payload,
        discord_url=safe_url,
        discord_media=media_filter,
        discord_asset=asset_filter,
        discord_unicode_emoji=_unicode_emoji_filter,
        discord_color=hex_color,
    )
    env.globals.update(
        _discord_html={"twemoji_base": twemoji or None, "videos": videos},
        discord_timestamp=discord_timestamp,
        discord_color_rule=discord_color_rule,
        discord_colors=colors,
        discord_state_color=lambda state: hex_color(state_color(state)),
        discord_styles=discord_styles,
        discord_scripts=discord_scripts,
    )
    return env
