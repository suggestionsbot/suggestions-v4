# discord_html

Render Discord Components V2 messages, such as the Hikari builders returned by
`Suggestions.as_components()`, as HTML with Jinja.

It works from the Discord payload (`builder.build()`), so anything you can send
to Discord renders here without per-message template code.

## Setup

```python
import jinja2
import discord_html

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), autoescape=True)
discord_html.setup_jinja(env)   # adds discord/ templates, filters and globals
```

Your loader keeps priority; the component templates are added as a fallback.

## Rendering a suggestion

```python
components = await suggestion.as_components(..., exclude_buttons=False)

html = env.get_template("suggestion.html").render(
    components=components,          # Hikari builders, payload dicts, or a mix
    discord_ctx=discord_html.DiscordContext(
        users={suggestion.author_id: author_display_name},
        channels={channel_id: "suggestions"},
        roles={role_id: "Moderators"},
        role_colors={role_id: 0xE67E22},
    ),
)
```

```jinja
{# suggestion.html #}
{% import "discord/components.html.j2" as discord with context %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  {{ discord_styles() }}           {# or link static/discord-components.css #}
</head>
<body>
  {{ discord.message(components) }}
  {{ discord_scripts() }}          {# optional: local-time timestamps, sticky spoilers #}
</body>
</html>
```

`discord_ctx` may be a `DiscordContext` or a plain dict with the same keys.
`with context` is required so the markdown filter can read `discord_ctx`.
Without it, mentions render as `@unknown-user` and so on.

### Looking like Discord

The defaults are measured from Discord's desktop client. To match a real message:

```python
discord_html.setup_jinja(env, twemoji=True)   # Unicode emoji as Twemoji, like Discord
                                              # (or twemoji="https://your.cdn/twemoji/svg/")
```

```jinja
<html lang="en-NZ" data-dc-hour-cycle="h23">   {# 24h clock, as in Discord's settings #}
...
{{ discord.message(
     components,
     author={"name": "Suggestions", "avatar_url": bot_avatar_url,
             "color": 0xFFD663, "app": True, "verified": True},
     timestamp=message.created_at,
     edited=message.edited_at is not none,
) }}
```

* `--dc-font-size` mirrors Discord's chat font scaling (default `16px`;
  `.dc-message { --dc-font-size: 14px }` for the compact size).
* Discord's own font (gg sans) isn't redistributable, so text falls back to
  Noto Sans / Helvetica / Arial and may wrap a word or two differently.
  If you have a licence, load it under the name `"gg sans"`.

### `discord.message(components, interactive=false, theme=none, author=none, timestamp=none, edited=false)`

* `interactive` – buttons look clickable and carry `data-custom-id`
  (`v4_suggestions_up_vote:<sID>`) so you can wire up voting from the web.
  Off by default: buttons render as static, read-only.
* `theme` – `"light"` or `"dark"` to override the OS preference.

`discord.component(payload_dict)` renders a single component if you want to build your
own layout around parts of a message.

## What's supported

| Component | Notes |
|---|---|
| Container (17) | accent colour bar, spoiler blur |
| Text Display (10) | Discord markdown, see below |
| Section (9) | text + thumbnail/button accessory |
| Separator (14) | divider on/off, small/large spacing |
| Media Gallery (12) | 1–10 items, Discord-like grid |
| Thumbnail (11), File (13) | spoilers supported |
| Action Row (1), Button (2) | all styles, custom/unicode emoji, link buttons |
| Selects (3, 5–8) | static placeholder |

Markdown supports headings, `-#` subtext, bold, italic, underline, strikethrough,
spoilers, inline and fenced code, `>` and `>>>` quotes, nested lists, masked/bare/`<suppressed>`
links, user/role/channel/slash-command mentions, `@everyone`/`@here`, custom emoji,
`<t:…:style>` timestamps, and backslash escapes.

## Suggestions palette

The bot's colours live in `discord_html.colors` (`PENDING_COLOR`, `APPROVED_COLOR`,
`REJECTED_COLOR`, `IMPLEMENTED_COLOR`, `DUPLICATE_COLOR`, `ERROR_COLOR`, `EMBED_COLOR`).
Messages don't need them: the accent comes from the container's `accent_color`.
They're for the rest of your page:

```jinja
<span class="dc-state dc-state-{{ suggestion.state.value }}">{{ suggestion.state.value|title }}</span>
<h2 style="color: {{ discord_state_color(suggestion.state) }}">…</h2>
```

```css
.my-filter.approved { border-color: var(--dc-color-approved); }   /* on :root */
```

Keep `colors.py` in sync if the bot's constants change.

## Strict Content-Security-Policy (nonce-based)

The library works under a CSP with no `'unsafe-inline'`:

* Colours (accents, role and author colours) are set with small `<style>` elements, never
  `style=""` attributes. They and `discord_styles()` / `discord_scripts()` carry the page's
  nonce, read automatically from a `csp_nonce` template variable.
* Or serve `STATIC_DIR` and include the files with your nonce:
  `<link rel="stylesheet" href="/discord-html/discord-components.css" nonce="{{ csp_nonce }}">`.
* **Browsers ignore nonces on `<img>` and `<video>`**, so media must come from origins the
  CSP lists. Use `media_url` to rewrite media to a same-origin route (fits `img-src 'self'`),
  and return `None` for anything the page can't load; it becomes a link instead of a broken
  image.
* With no `media-src`, videos can't play at all: use `setup_jinja(env, videos="link")`.
* Self-host Twemoji (`twemoji="/static/twemoji/"`) to keep it on `'self'`.

## Proxying user images

Suggestion images are user-supplied URLs, so rendering them as-is makes every
viewer's browser request an arbitrary host (leaking their IP). Rewrite them:

```python
discord_html.setup_jinja(env, media_url=lambda url: f"/img-proxy?u={quote(url, safe='')}")
```

The rewritten URL is checked again: it must be http(s) or a same-origin path
(`/...`). URLs coming from message payloads themselves must be absolute http(s).

## Safety

All user text is HTML-escaped before markup is added, and every URL in `href`/`src`
must be `http(s)`, so `javascript:` links and injected attributes don't get through.
This holds whether or not your environment uses `autoescape`.

* Masked links whose label *looks like* a URL or domain (`[paypal.com](https://evil.com)`,
  including via formatting, escapes or look-alike Unicode) render as
  `paypal.com (https://evil.com)`, so the label can't disguise the destination.
* All regexes are linear-time on hostile input; 40k-character attack strings render in milliseconds.
* Images, emoji and links send no `Referer`, so external hosts don't learn your page URLs.
* Names from `DiscordContext` are bidi-isolated, so a name containing an RTL override
  can't flip the surrounding text.
* Component nesting is capped (8 levels) and list nesting at 10, so hostile payloads
  can't exhaust recursion or produce absurdly deep DOM.
* Server-rendered times are labelled `UTC`; with `discord_scripts()` they're shown in the
  viewer's own time zone. `DiscordContext.now` may be naive (treated as server-local).
* With the script loaded, spoilers reveal only on click/Enter/Space, not on tab focus.
* Spoilers are hidden visually only. The text is still in the HTML, so don't rely on it on
  public pages for anything that must stay hidden.
* `discord_styles()` / `discord_scripts()` emit inline `<style>`/`<script>`. Under a strict
  Content-Security-Policy, serve the files from `STATIC_DIR` instead.

## Filters & globals

| Name | Purpose |
|---|---|
| `|discord_markdown` | Discord markdown → safe HTML |
| `|discord_payload` | builders/dicts → payload dicts |
| `|discord_url` | URL if http(s), else `""` |
| `|discord_color` | `0x4CAF50` → `#4caf50` |
| `|discord_unicode_emoji` | a Unicode emoji, as Twemoji if enabled |
| `discord_timestamp(dt_or_unix, style="S")` | localised `<time>` element |
| `discord_styles()` / `discord_scripts()` | inline CSS / JS |

Static files are in `discord_html/static/` (`discord_html.STATIC_DIR`) if you'd
rather serve them than inline them.
