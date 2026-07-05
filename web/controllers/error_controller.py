from bot.tables import InternalErrors
from litestar import Controller, get, Request
from litestar.response import Template, Redirect

from web.middleware import EnsureAdmin
from web.util import html_template, alert


class ErrorController(Controller):
    middleware = [EnsureAdmin]  # noqa: RUF012
    include_in_schema = False
    path = "/errors"

    @get(path="/{error_id:str}", name="view_error_info")
    async def view_error_info(
        self, request: Request, error_id: str
    ) -> Template | Redirect:
        internal_error = await InternalErrors.objects().get(InternalErrors.id == error_id)
        if internal_error is None:
            alert(request, "Requested Error does not exist", level="error")
            return Redirect("/")

        return html_template("errors/view.jinja", context={"error": internal_error})
