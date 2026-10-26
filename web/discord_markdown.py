"""Render user-submitted text with the subset of markdown Discord supports.

Anything Discord would show literally (tables, images, raw HTML, footnotes,
horizontal rules, #### headings, reference links...) stays as text here too.
"""

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from markupsafe import Markup
from wenmode import HTMLRenderer, Parser, Wenmode
from wenmode.nodes import Blockquote, Code, Heading, ListItem, Node, Paragraph, Parent
from wenmode.nodes import Link as LinkNode
from wenmode.nodes import List as ListNode
from wenmode.plugins import InlineDelimited
from wenmode.renderers import RenderContext
from wenmode.rules import (
    AtxHeading,
    Autolink,
    BackslashEscape,
    BlockCandidate,
    BlockRule,
    Emphasis,
    ExtendedAutolink,
    FencedCode,
    InlineCandidate,
    InlineCode,
    InlineRule,
    Link,
    List,
    Strikethrough,
)
from wenmode.state import BlockState

# Bidi overrides/isolates can make text read differently from what it links to.
_BIDI_CONTROLS = dict.fromkeys(
    map(ord, "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
)
_GAP = '<span class="dc-gap"></span>'
# Letters that render as nothing: Hangul fillers and the blank braille pattern.
_BLANK_CHARS = frozenset("\u115f\u1160\u3164\uffa0\u2800")
# Domain name, IPv4, or IPv6 (urlsplit drops the brackets).
_HOST = re.compile(r"[a-z0-9_-]+(?:\.[a-z0-9_-]+)*\.?|[0-9a-f:.]+")


@dataclass
class Spoiler(Parent):
    type: str = "spoiler"


@dataclass
class Underline(Parent):
    type: str = "underline"


@dataclass
class UnderlineItalic(Parent):
    type: str = "underlineItalic"


@dataclass
class Subtext(Parent):
    type: str = "subtext"


@dataclass
class Token(Node):
    """<t:...>, <:emoji:id>, <@id>, <@&id>, <#id>, @everyone and @here."""

    type: str = "discordToken"
    raw: str = ""
    groups: dict[str, str | None] = field(default_factory=dict)


class DiscordHeading(AtxHeading):
    # Only # to ###, at the start of the line, with text after a space.
    pattern = r"#{1,3}[ \t]+(?=\S)"

    def parse(
        self,
        parser: Parser,
        state: BlockState,
        candidate: BlockCandidate,  # noqa: ARG002
    ) -> Heading:
        # Not AtxHeading.parse: it strips a closing "#" run, Discord keeps it.
        marker, text = state.line.rstrip("\n").split(maxsplit=1)
        state.advance()
        return Heading(
            depth=len(marker), children=parser.parse_inlines(text.strip(), state)
        )


class DiscordList(List):
    # Only "-", "*" and "1." start a list, and an item needs text.
    pattern = r"(?:[*-]|\d{1,9}\.)[ \t]+(?=\S)"


class SubtextRule(BlockRule):
    name = "subtext"
    pattern = r"-#[ \t]+(?=\S)"

    def parse(
        self,
        parser: Parser,
        state: BlockState,
        candidate: BlockCandidate,  # noqa: ARG002
    ) -> Subtext:
        text = state.line.rstrip("\n")[2:].strip()
        state.advance()
        return Subtext(children=parser.parse_inlines(text, state))


class DiscordQuote(BlockRule):
    """'> ' quotes one line, '>>> ' quotes the rest of the message.

    No lazy continuation and no nesting: a '>' inside a quote is just text.
    """

    name = "discord_quote"
    pattern = r">(?:>>)? "

    def parse(
        self,
        parser: Parser,
        state: BlockState,
        candidate: BlockCandidate,  # noqa: ARG002
    ) -> Blockquote:
        lines = []
        if state.line.startswith(">>> "):
            lines.append(state.line[4:])
            state.advance()
            while not state.done:
                lines.append(state.line)
                state.advance()
        else:
            while not state.done and state.line.startswith("> "):
                lines.append(state.line[2:])
                state.advance()
        text = "".join("\\" + line if line.startswith(">") else line for line in lines)
        return Blockquote(children=parser.parse_blocks(text, parent_state=state))


class BareUrl(ExtendedAutolink):
    # Discord only links bare http(s) URLs, not www. or emails.
    def search_url(self, text: str, pos: int) -> re.Match[str] | None:
        match = super().search_url(text, pos)
        while match is not None and not match[0].lower().startswith(
            ("http://", "https://")
        ):
            match = super().search_url(text, match.start() + 1)
        return match

    def search_email(self, text: str, pos: int) -> None:  # noqa: ARG002
        return None


class DiscordToken(InlineRule):
    name = "discord_token"
    pattern = (
        r"<(?:t:(?P<ts>-?\d{1,13})(?::(?P<style>[tTdDfFRS]))?"
        r"|(?P<animated>a?):(?P<emoji>\w{2,32}):(?P<emoji_id>\d{1,20})"
        r"|@!?(?P<user>\d{1,20})|@&(?P<role>\d{1,20})|#(?P<channel>\d{1,20}))>"
        r"|(?<!\w)@(?P<everyone>everyone|here)\b"
    )

    def parse(
        self,
        parser: Parser,  # noqa: ARG002
        text: str,  # noqa: ARG002
        candidate: InlineCandidate,
        state: BlockState,  # noqa: ARG002
    ) -> tuple[Token | None, int]:
        match = candidate.match
        if match is None:
            return None, candidate.start
        return Token(raw=match[0], groups=match.groupdict()), match.end()


class DiscordRenderer(HTMLRenderer):
    # Discord only makes absolute http(s) links clickable.
    allowed_url_schemes = frozenset({"http", "https"})

    def sanitize_url(self, value: str) -> str | None:
        # wenmode allows relative URLs, which would let "//evil.com" or
        # "/guilds/..." render as links. Require an absolute http(s) URL,
        # without "https://google.com@evil.com" style credentials.
        url = super().sanitize_url(value)
        if url is None:
            return None
        try:
            parts = urlsplit(url)
        except ValueError:
            return None
        if parts.scheme.lower() not in self.allowed_url_schemes or _host(url) is None:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        return url


def _children(renderer: HTMLRenderer, node: Parent, context: RenderContext) -> str:
    return renderer.render_children(node.children, context)


def _plain_text(node: Node) -> str:
    if isinstance(node, Parent):
        return "".join(_plain_text(child) for child in node.children)
    return getattr(node, "value", None) or getattr(node, "raw", "")


def _is_invisible(text: str) -> bool:
    return all(
        ch.isspace()
        or ch in _BLANK_CHARS
        or unicodedata.category(ch) in {"Cf", "Cc", "Mn", "Me"}
        for ch in text
    )


def _unlink(node: Parent) -> None:
    """Replace links nested in node with their text: no <a> inside <a>."""
    children: list[Node] = []
    for child in node.children:
        if not isinstance(child, Parent):
            children.append(child)
            continue
        _unlink(child)
        if child.type == "link":
            children.extend(child.children)
        else:
            children.append(child)
    node.children = children


def _host(href: str) -> str | None:
    """The host a browser would go to, or None if a browser would reject it.

    Percent-decoded first: "evil.com%2F.google.com" is not a host, so the
    link isn't shown as one.
    """
    try:
        host = unquote(urlsplit(href).hostname or "")
        host = host.encode("idna").decode("ascii")  # lookalike domains show as xn--
    except (ValueError, UnicodeError):
        return None
    return host if _HOST.fullmatch(host) else None


def _link(renderer: HTMLRenderer, node: LinkNode, context: RenderContext) -> str:
    href = renderer.sanitize_url(node.url)
    if href is None:
        return _children(renderer, node, context)
    _unlink(node)
    attrs = {
        "class": "dc-link",
        "href": href,
        "target": "_blank",
        "rel": "noopener noreferrer nofollow",
    }
    label = _plain_text(node)
    if _is_invisible(label):
        # An empty or invisible label would hide the link, so show where it goes.
        return f"<a{renderer.render_attrs(attrs)}>{renderer.escape_html(href)}</a>"

    html = f"<a{renderer.render_attrs(attrs)}>{_children(renderer, node, context)}</a>"
    host = _host(href)
    if host is None or label.strip().lower().rstrip("/") in {
        href.lower().rstrip("/"),
        host,
    }:
        return html
    # Masked link: Discord warns before opening these, we show the real host.
    return f'{html} <span class="dc-link-host">({renderer.escape_html(host)})</span>'


def _heading(renderer: HTMLRenderer, node: Heading, context: RenderContext) -> str:
    # Not <h1>-<h3>: user text shouldn't join the page's heading outline.
    return f'<p class="dc-h{node.depth}">{_children(renderer, node, context)}</p>'


def _code(
    renderer: HTMLRenderer,
    node: Code,
    context: RenderContext,  # noqa: ARG001
) -> str:
    code = renderer.escape_html(node.value)
    return f'<pre class="dc-codeblock"><code>{code}</code></pre>'


def _list(renderer: HTMLRenderer, node: ListNode, context: RenderContext) -> str:
    tag = "ol" if node.ordered else "ul"
    start = (
        f' start="{int(node.start)}"'
        if node.ordered and node.start not in (None, 1)
        else ""
    )
    # Discord lists are always tight: no <p> around each item.
    items = []
    for item in node.children:
        assert isinstance(item, ListItem)
        content = "".join(
            (
                _children(renderer, child, context)
                if isinstance(child, Paragraph)
                else renderer.render_children([child], context)
            )
            for child in item.children
        )
        items.append(f"<li>{content}</li>")
    return f'<{tag} class="dc-list"{start}>{"".join(items)}</{tag}>'


def _token(
    renderer: HTMLRenderer,
    node: Token,
    context: RenderContext,  # noqa: ARG001
) -> str:
    g = node.groups
    esc = renderer.escape_html
    if g["ts"] is not None:
        try:
            when = dt.datetime.fromtimestamp(int(g["ts"]), dt.UTC)
        except (OverflowError, OSError, ValueError):
            return esc(node.raw)
        # Same as suggestions_controller.timestamp(): UTC text until the script runs.
        return (
            f'<time class="dc-timestamp" data-dc-ts="{int(g["ts"])}"'
            f' datetime="{when.isoformat()}" data-dc-style="{esc(g["style"] or "f")}">'
            f"{when.strftime('%d %b %Y, %H:%M UTC')}</time>"
        )
    if g["emoji_id"] is not None:
        ext = "gif" if g["animated"] else "webp"
        return (
            f'<img class="dc-emoji" src="https://cdn.discordapp.com/emojis/'
            f'{esc(g["emoji_id"])}.{ext}?size=48" alt=":{esc(g["emoji"] or "")}:"'
            ' draggable="false" loading="lazy" referrerpolicy="no-referrer">'
        )
    # We only have ids, not names: same as a legacy "<@123>" submitter.
    if g["channel"] is not None:
        label = f"#{esc(g['channel'])}"
    elif g["everyone"] is not None:
        label = f"@{esc(g['everyone'])}"
    else:
        label = f"@{esc(g['user'] or g['role'] or '')}"
    return f'<span class="dc-mention"><bdi>{label}</bdi></span>'


_markdown = Wenmode(
    [
        FencedCode,
        DiscordQuote,
        SubtextRule,  # before DiscordList, or "-# x" parses as a list item
        DiscordList,
        DiscordHeading,
        DiscordToken,  # before Autolink, which also starts at "<"
        Autolink,
        BackslashEscape,
        Link(references=False),
        InlineCode,
        InlineDelimited(name="spoiler", node=Spoiler, opener="||", closer="||"),
        # Discord reads "___x___" as underlined italics, not nested emphasis.
        InlineDelimited(
            name="underline_italic", node=UnderlineItalic, opener="___", closer="___"
        ),
        InlineDelimited(name="underline", node=Underline, opener="__", closer="__"),
        Strikethrough(allow_single_tilde=False),
        Emphasis,
        BareUrl,
    ],
    # Newlines stay as text: .dc-md is white-space: pre-wrap, like Discord.
    renderer=DiscordRenderer(soft_break="newline"),
    positions=True,
)
_markdown.register_renderer_handlers(
    {
        "html": {
            "spoiler": lambda r, n, c: (
                f'<span class="dc-spoiler" tabindex="0">{_children(r, n, c)}</span>'
            ),
            "underline": lambda r, n, c: f"<u>{_children(r, n, c)}</u>",
            "underlineItalic": lambda r, n, c: f"<u><em>{_children(r, n, c)}</em></u>",
            "subtext": lambda r, n, c: f'<p class="dc-subtext">{_children(r, n, c)}</p>',
            "inlineCode": lambda r, n, c: (  # noqa: ARG005
                f'<code class="dc-code">{r.escape_html(n.value)}</code>'
            ),
            "blockquote": lambda r, n, c: (
                f'<blockquote class="dc-quote">{_children(r, n, c)}</blockquote>'
            ),
            "paragraph": lambda r, n, c: f"<p>{_children(r, n, c)}</p>",
            "discordToken": _token,
            "link": _link,
            "heading": _heading,
            "code": _code,
            "list": _list,
        }
    }
)


def render(text: str) -> Markup:
    """Escapes raw HTML and drops non-http(s) URLs, so the result is safe to mark up."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(_BIDI_CONTROLS)
    tree = _markdown.parse(text)
    # Markdown collapses blank lines between blocks; Discord shows every one.
    parts = []
    previous = None
    for block in tree.children:
        if previous is not None and previous.position and block.position:
            gap = text[previous.position.end : block.position.start]
            parts.append(_GAP * gap.count("\n"))
        parts.append(_markdown.render_node(block))
        previous = block
    return Markup("".join(parts))  # noqa: S704
