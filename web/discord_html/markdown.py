"""Render Discord-flavoured markdown to safe HTML.

All user text is HTML-escaped before any markup is added, so the output of
:func:`render_markdown` is always safe to place in a page.
"""

from __future__ import annotations

import datetime as dt
import html as _html
import re
import unicodedata
from dataclasses import dataclass, field

from markupsafe import Markup, escape

EMOJI_CDN = "https://cdn.discordapp.com/emojis/{id}.{ext}?size=48"
MAX_LIST_DEPTH = 10
TWEMOJI_BASE = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/svg/"


@dataclass
class DiscordContext:
    """Lookups used to turn raw IDs into readable names.

    Anything not found falls back to a generic label, so all fields are optional.
    """

    users: dict[int, str] = field(default_factory=dict)
    roles: dict[int, str] = field(default_factory=dict)
    role_colors: dict[int, int] = field(default_factory=dict)
    channels: dict[int, str] = field(default_factory=dict)
    now: dt.datetime | None = None  # used for <t:..:R>; defaults to current UTC time


DEFAULT_CONTEXT = DiscordContext()


# ---------------------------------------------------------------- timestamps


def _clock(d: dt.datetime, seconds: bool = False) -> str:
    hour = d.hour % 12 or 12
    suffix = "AM" if d.hour < 12 else "PM"
    return f"{hour}:{d:%M}{':' + f'{d:%S}' if seconds else ''} {suffix}"


def _relative(when: dt.datetime, now: dt.datetime) -> str:
    delta = (when - now).total_seconds()
    seconds = abs(delta)
    for name, size in (
        ("year", 31_536_000),
        ("month", 2_592_000),
        ("day", 86_400),
        ("hour", 3_600),
        ("minute", 60),
    ):
        if seconds >= size:
            n = int(seconds // size)
            break
    else:
        name, n = "second", int(seconds)
    unit = name if n == 1 else name + "s"
    return f"in {n} {unit}" if delta > 0 else f"{n} {unit} ago"


def timestamp_html(ts: int, style: str = "f", now: dt.datetime | None = None) -> str | None:
    """``<time>`` element for a unix timestamp; None if it's out of range."""
    try:
        iso = dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()
        text = format_timestamp(ts, style, now)
    except (OverflowError, OSError, ValueError):
        return None
    return (
        f'<time class="dc-timestamp" datetime="{iso}" data-dc-ts="{ts}" '
        f'data-dc-style="{escape(style)}">{text}</time>'
    )


def format_timestamp(ts: int, style: str, now: dt.datetime | None = None) -> str:
    """Server-side fallback text (UTC). The optional script localises it."""
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.astimezone()  # naive datetimes are treated as server-local time
    date_long = f"{d:%B} {d.day}, {d.year}"
    # Times are labelled UTC so viewers without JS (which localises them)
    # aren't silently shown a time that's hours off.
    return {
        "t": f"{_clock(d)} UTC",
        "T": f"{_clock(d, seconds=True)} UTC",
        "d": f"{d.month}/{d.day}/{d.year}",
        "D": date_long,
        "f": f"{date_long} {_clock(d)} UTC",
        "F": f"{d:%A}, {date_long} {_clock(d)} UTC",
        "R": _relative(d, now),
        "S": f"{d:%Y-%m-%d %H:%M} UTC",  # message-header style, localised by the script
    }.get(style, f"{date_long} {_clock(d)} UTC")


# ---------------------------------------------------------------- patterns

# Code spans and backslash escapes in ONE left-to-right pass, so an escaped
# backtick (\`) can never open a code span and backslashes inside code stay literal.
_LITERALS = re.compile(
    r"```(?:([\w+#.-]+)\n)?\n?(.*?)\n?```"   # 1 lang, 2 code block body
    r"|``([^\n]+?)``"                         # 3 double-backtick inline code
    r"|`([^`\n]+)`"                           # 4 inline code
    r"|\\([\\*_~|`>#\-\[\]()<:@])",          # 5 backslash-escaped character
    re.DOTALL,
)

_HEADING = re.compile(r"^(#{1,3}) +(.+)$")
_SUBTEXT = re.compile(r"^-# +(.+)$")
_LIST = re.compile(r"^( *)(?:[-*]|([0-9]{1,9})\.) +(.*)$")
_QUOTE = re.compile(r"^&gt;(?: (.*))?$")
_QUOTE_REST = "&gt;&gt;&gt; "

_MASKED_LINK = re.compile(r"\[([^\[\]\n]+)\]\((https?://[^\s)\x00]+)\)")
_SUPPRESSED_LINK = re.compile(r"&lt;(https?://[^\s\x00]+?)&gt;")
_BARE_LINK = re.compile(r"https?://(?:(?!&lt;|&gt;)[^\s\x00])+")
_USER = re.compile(r"&lt;@!?([0-9]{1,20})&gt;")
_ROLE = re.compile(r"&lt;@&amp;([0-9]{1,20})&gt;")
_CHANNEL = re.compile(r"&lt;#([0-9]{1,20})&gt;")
_EMOJI = re.compile(r"&lt;(a?):([A-Za-z0-9_]{2,32}):([0-9]{1,20})&gt;")
_TIMESTAMP = re.compile(r"&lt;t:(-?[0-9]{1,13})(?::([tTdDfFR]))?&gt;")
_SLASH = re.compile(r"&lt;/([\w -]{1,100}):([0-9]{1,20})&gt;")
_EVERYONE = re.compile(r"(?<![\w@.])@(everyone|here)\b")

# Each match is stashed with its inner text formatted recursively, so tags are
# always properly nested and later patterns can't match across earlier tags.
# Single-delimiter italics exclude their delimiter from the body, which keeps
# them linear-time on inputs like "*a *a *a ...".
# Unicode emoji, for optional Twemoji rendering (what Discord itself shows).
# Emoji_Presentation characters always count; text-default ones (©, ↔, ☺, …)
# only when followed by VS16 or a skin-tone modifier, as in Discord.
_EMOJI_PRES = (
    "\u231a\u231b\u23e9-\u23ec\u23f0\u23f3\u25fd\u25fe\u2614\u2615\u2648-\u2653"
    "\u267f\u2693\u26a1\u26aa\u26ab\u26bd\u26be\u26c4\u26c5\u26ce\u26d4\u26ea"
    "\u26f2\u26f3\u26f5\u26fa\u26fd\u2705\u270a\u270b\u2728\u274c\u274e"
    "\u2753-\u2755\u2757\u2795-\u2797\u27b0\u27bf\u2b1b\u2b1c\u2b50\u2b55"
    "\U0001f004-\U0001faff"
)
_EMOJI_TEXT = (
    "\u00a9\u00ae\u203c\u2049\u2122\u2139\u2194-\u2199\u21a9\u21aa\u2328\u23cf"
    "\u23ed-\u23ef\u23f1\u23f2\u23f8-\u23fa\u24c2\u25aa\u25ab\u25b6\u25c0"
    "\u25fb\u25fc\u2600-\u27bf\u2934\u2935\u2b05-\u2b07\u3030\u303d\u3297\u3299"
)
_SKIN = "\U0001f3fb-\U0001f3ff"
_EMOJI_ATOM = (
    f"(?:[{_EMOJI_PRES}]\ufe0f?|[{_EMOJI_TEXT}](?:\ufe0f|(?=[{_SKIN}])))"
    f"[{_SKIN}]?[\U000e0020-\U000e007f]*"
)
_EMOJI_ZWJ_PART = f"[{_EMOJI_PRES}{_EMOJI_TEXT}]\ufe0f?[{_SKIN}]?"
_UNICODE_EMOJI = re.compile(
    "[\U0001f1e6-\U0001f1ff]{2}"                 # flags
    "|[#*0-9]\ufe0f?\u20e3"                        # keycaps
    f"|{_EMOJI_ATOM}(?:\u200d{_EMOJI_ZWJ_PART})*"   # everything else, incl. ZWJ sequences
)


def twemoji_code(sequence: str) -> str:
    """Twemoji's file name for an emoji: hex codepoints joined by '-'.
    VS16 is dropped unless the sequence contains a ZWJ (Twemoji's own rule)."""
    if "\u200d" not in sequence:
        sequence = sequence.replace("\ufe0f", "")
    return "-".join(f"{ord(ch):x}" for ch in sequence)


def twemoji_img(sequence: str, base: str) -> str:
    alt = escape(sequence)
    return (
        f'<img class="dc-emoji dc-twemoji" src="{escape(base)}{twemoji_code(sequence)}.svg" '
        f'alt="{alt}" draggable="false" loading="lazy" referrerpolicy="no-referrer">'
    )


_FORMATTING = (
    (re.compile(r"\*\*\*(.+?)\*\*\*"), "<strong><em>", "</em></strong>"),
    (re.compile(r"___(.+?)___"), "<u><em>", "</em></u>"),
    (re.compile(r"\*\*(.+?)\*\*"), "<strong>", "</strong>"),
    (re.compile(r"__(.+?)__"), "<u>", "</u>"),
    (re.compile(r"\*(?![\s*])([^*]*?[^\s*]|[^\s*])\*"), "<em>", "</em>"),
    (re.compile(r"(?<![A-Za-z0-9_])_(?![\s_])([^_]*?[^\s_]|[^\s_])_(?![A-Za-z0-9_])"), "<em>", "</em>"),
    (re.compile(r"~~(.+?)~~"), "<s>", "</s>"),
    (re.compile(r"\|\|(.+?)\|\|"), '<span class="dc-spoiler" tabindex="0">', "</span>"),
)
# Anything in a link label that reads like a URL or domain ("good.com",
# "paypal.com/login", "https://..."), checked against the label's visible,
# Unicode-normalised text so formatting, escapes and look-alike characters
# can't hide it.
_LOOKS_LIKE_URL = re.compile(
    r"[a-z][a-z0-9+.-]*:/|www\.|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:[/:?#]|\b)",
    re.IGNORECASE,
)
_DOT_LOOKALIKES = str.maketrans({"\u3002": ".", "\uff61": ".", "\u2024": ".", "\ufe52": ".", "\u06d4": "."})
_TAG = re.compile(r"<[^>]*>")
_PLACEHOLDER = re.compile(r"\x00(\d+)\x00")


class _Renderer:
    def __init__(
        self, ctx: DiscordContext, twemoji_base: str | None = None, nonce: str | None = None
    ) -> None:
        self.ctx = ctx
        self.twemoji_base = twemoji_base
        self.nonce = nonce
        self.stash: list[str] = []

    def hold(self, html: str) -> str:
        self.stash.append(html)
        return f"\x00{len(self.stash) - 1}\x00"

    # ------------------------------------------------------------ entry
    def render(self, text: str) -> str:
        text = text.replace("\x00", "").replace("\r\n", "\n").strip("\n")

        text = _LITERALS.sub(self._literal, text)
        text = str(escape(text))

        html = "".join(self._blocks(text.split("\n")))
        while _PLACEHOLDER.search(html):
            html = _PLACEHOLDER.sub(lambda m: self.stash[int(m[1])], html)
        return html

    def _literal(self, m: re.Match) -> str:
        if m[2] is not None:
            lang = f' class="language-{escape(m[1])}"' if m[1] else ""
            return self.hold(f'<pre class="dc-codeblock"><code{lang}>{escape(m[2])}</code></pre>')
        if m[3] is not None or m[4] is not None:
            return self.hold(f'<code class="dc-code">{escape(m[3] or m[4])}</code>')
        return self.hold(str(escape(m[5])))

    # ------------------------------------------------------------ blocks
    def _blocks(self, lines: list[str], allow_quote: bool = True) -> list[str]:
        out: list[str] = []
        para: list[str] = []

        def flush() -> None:
            if para:
                body = "<br>".join(self._inline(line) for line in para)
                out.append(f'<div class="dc-p">{body}</div>')
                para.clear()

        i = 0
        while i < len(lines):
            line = lines[i]
            if allow_quote and line.startswith(_QUOTE_REST):
                flush()
                inner = [line[len(_QUOTE_REST):], *lines[i + 1:]]
                out.append(self._quote(inner))
                break
            if allow_quote and _QUOTE.match(line):
                flush()
                inner = []
                while i < len(lines) and (q := _QUOTE.match(lines[i])):
                    inner.append(q[1] or "")
                    i += 1
                out.append(self._quote(inner))
                continue
            if m := _HEADING.match(line):
                flush()
                level = len(m[1])
                out.append(f'<h{level} class="dc-h{level}">{self._inline(m[2])}</h{level}>')
            elif m := _SUBTEXT.match(line):
                flush()
                out.append(f'<div class="dc-subtext">{self._inline(m[1])}</div>')
            elif _LIST.match(line):
                flush()
                items = []
                while i < len(lines) and (li := _LIST.match(lines[i])):
                    items.append((len(li[1]), li[2], li[3]))
                    i += 1
                out.append(self._list(items))
                continue
            else:
                para.append(line)
            i += 1
        flush()
        return out

    def _quote(self, lines: list[str]) -> str:
        return f'<blockquote class="dc-quote">{"".join(self._blocks(lines, False))}</blockquote>'

    def _list(self, items: list[tuple[int, str | None, str]]) -> str:
        html: list[str] = []
        stack: list[tuple[int, str]] = []
        for indent, number, content in items:
            while stack and indent < stack[-1][0]:
                html.append(f"</li></{stack.pop()[1]}>")
            if not stack or (indent > stack[-1][0] and len(stack) < MAX_LIST_DEPTH):
                tag = "ol" if number else "ul"
                start = f' start="{int(number)}"' if number and int(number) != 1 else ""
                html.append(f'<{tag} class="dc-list"{start}><li>')
                stack.append((indent, tag))
            else:
                html.append("</li><li>")
            html.append(self._inline(content))
        while stack:
            html.append(f"</li></{stack.pop()[1]}>")
        return "".join(html)

    # ------------------------------------------------------------ inline
    def _link(self, url: str, label: str) -> str:
        return self.hold(
            f'<a class="dc-link" href="{url}" target="_blank" rel="noopener noreferrer nofollow">'
            f"{label}</a>"
        )

    def _resolve(self, s: str) -> str:
        while _PLACEHOLDER.search(s):
            s = _PLACEHOLDER.sub(lambda m: self.stash[int(m[1])], s)
        return s

    def _visible_text(self, html: str) -> str:
        text = _html.unescape(_TAG.sub("", self._resolve(html)))
        return unicodedata.normalize("NFKC", text).translate(_DOT_LOOKALIKES)

    def _masked_link(self, m: re.Match) -> str:
        label = self._format(m[1])
        url = m[2]
        if _LOOKS_LIKE_URL.search(self._visible_text(label)):
            # "[good.com](https://evil.com)": keep the label as plain text and
            # show the real destination next to it.
            return self.hold(f'<span class="dc-link-label">{self._resolve(label)}</span> (') + self._link(url, url) + self.hold(")")
        return self._link(url, label)

    def _bare_link(self, m: re.Match) -> str:
        url = m[0]
        opens, closes = url.count("("), url.count(")")
        end = len(url)
        while end and url[end - 1] in ".,:;!?)]":
            if url[end - 1] == ")":
                if opens >= closes:
                    break  # balanced, e.g. https://en.wikipedia.org/wiki/Foo_(bar)
                closes -= 1
            end -= 1
        return self._link(url[:end], url[:end]) + url[end:]

    def _inline(self, s: str) -> str:
        ctx = self.ctx
        s = _MASKED_LINK.sub(self._masked_link, s)
        s = _SUPPRESSED_LINK.sub(lambda m: self._link(m[1], m[1]), s)
        s = _BARE_LINK.sub(self._bare_link, s)

        s = _ROLE.sub(self._role, s)
        s = _USER.sub(
            lambda m: self.hold(
                f'<span class="dc-mention">@<bdi>{escape(ctx.users.get(int(m[1]), "unknown-user"))}</bdi></span>'
            ),
            s,
        )
        s = _CHANNEL.sub(
            lambda m: self.hold(
                f'<span class="dc-mention">#<bdi>{escape(ctx.channels.get(int(m[1]), "unknown"))}</bdi></span>'
            ),
            s,
        )
        s = _SLASH.sub(
            lambda m: self.hold(f'<span class="dc-mention dc-command">/{m[1]}</span>'), s
        )
        s = _EVERYONE.sub(lambda m: self.hold(f'<span class="dc-mention">@{m[1]}</span>'), s)
        s = _EMOJI.sub(self._emoji, s)
        s = _TIMESTAMP.sub(self._timestamp, s)
        if self.twemoji_base:
            s = _UNICODE_EMOJI.sub(lambda m: self.hold(twemoji_img(m[0], self.twemoji_base)), s)
        return self._format(s)

    def _format(self, s: str) -> str:
        for pattern, open_tag, close_tag in _FORMATTING:
            s = pattern.sub(
                lambda m, o=open_tag, c=close_tag: self.hold(o + self._format(m[1]) + c), s
            )
        return s

    def _role(self, m: re.Match) -> str:
        role_id = int(m[1])
        name = escape(self.ctx.roles.get(role_id, "unknown-role"))
        color = _color_int(self.ctx.role_colors.get(role_id))
        if not color:
            return self.hold(f'<span class="dc-mention dc-role">@<bdi>{name}</bdi></span>')
        cls = f"dc-role-{color:06x}"
        # A <style> element rather than style="", so it works under a CSP without
        # 'unsafe-inline' (the nonce is the page's csp_nonce).
        return self.hold(
            color_rule(cls, "--dc-role", f"#{color:06x}", self.nonce)
            + f'<span class="dc-mention dc-role dc-role-colored {cls}">@<bdi>{name}</bdi></span>'
        )

    def _emoji(self, m: re.Match) -> str:
        url = EMOJI_CDN.format(id=m[3], ext="gif" if m[1] else "webp")
        return self.hold(
            f'<img class="dc-emoji" src="{url}" alt=":{m[2]}:" title=":{m[2]}:" '
            f'loading="lazy" draggable="false" referrerpolicy="no-referrer">'
        )

    def _timestamp(self, m: re.Match) -> str:
        html = timestamp_html(int(m[1]), m[2] or "f", self.ctx.now)
        return self.hold(html) if html else m[0]


_CSS_CLASS = re.compile(r"^[a-z0-9-]{1,64}$")
_CSS_COLOR = re.compile(r"^#[0-9a-f]{6}$")
_CSS_PROPS = {"--dc-role", "--dc-accent", "color"}


def color_rule(css_class: str, prop: str, color: str, nonce: str | None = None) -> str:
    """``<style>.css_class{prop:color}</style>`` with strict validation of every part,
    carrying a CSP nonce when given."""
    if not (_CSS_CLASS.match(css_class) and prop in _CSS_PROPS and _CSS_COLOR.match(color)):
        return ""
    nonce_attr = f' nonce="{escape(nonce)}"' if nonce else ""
    return f"<style{nonce_attr}>.{css_class}{{{prop}:{color}}}</style>"


def _color_int(value: object) -> int | None:
    """Accept 0xRRGGBB ints (incl. hikari.Color) or "#rrggbb"/"0xrrggbb" strings."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value & 0xFFFFFF
    if isinstance(value, str):
        try:
            return int(value.strip().removeprefix("#").removeprefix("0x"), 16) & 0xFFFFFF
        except ValueError:
            return None
    return None


def render_markdown(
    text: str | None,
    ctx: DiscordContext | None = None,
    *,
    twemoji_base: str | None = None,
    nonce: str | None = None,
) -> Markup:
    """Convert Discord markdown to an HTML-safe :class:`Markup` string.

    ``twemoji_base`` (a URL ending in "/") renders Unicode emoji as Twemoji
    images, matching Discord; without it they use the system emoji font.
    ``nonce`` is added to any ``<style>`` the output needs (role colours), for
    pages served with a nonce-based Content-Security-Policy.
    """
    if not text:
        return Markup("")
    return Markup(_Renderer(ctx or DEFAULT_CONTEXT, twemoji_base, nonce).render(str(text)))
