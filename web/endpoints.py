from litestar import get
from litestar.response import Template, Redirect
from starlette.requests import Request

from web.util import html_template, alert


@get(path="/", include_in_schema=False)
async def home() -> Template:
    return html_template(
        "home.jinja",
        {
            "title": "Landing page",
        },
    )


@get(
    path="/mock/link_oauth_accounts",
    name="link_oauth_accounts",
    include_in_schema=False,
)
async def mock_oauth(request: Request) -> Redirect:
    alert(request, "OAuth is not supported on this application")
    return Redirect("/")
