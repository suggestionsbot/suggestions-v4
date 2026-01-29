import hikari
from litestar import get
from litestar.response import Template, Redirect
from starlette.requests import Request

from shared.saq.worker import SAQ_QUEUE
from web import constants
from web.util import html_template, alert


@get(path="/", include_in_schema=False)
async def home(request: Request) -> Template:
    await SAQ_QUEUE.enqueue("test_message_send")
    async with constants.DISCORD_REST_CLIENT.acquire(
        constants.BOT_TOKEN, hikari.TokenType.BOT
    ) as client:
        await client.create_message(1459693890662830102, "litestar works as expected")
    return html_template("home.jinja", {"title": "Landing page"})


@get(
    path="/mock/link_oauth_accounts",
    name="link_oauth_accounts",
    include_in_schema=False,
)
async def mock_oauth(request: Request) -> Redirect:
    alert(request, "OAuth is not supported on this application")
    return Redirect("/")
