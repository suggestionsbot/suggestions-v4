from dotenv import load_dotenv
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler

from web.tables import APIToken

load_dotenv()


async def ensure_api_token(connection: ASGIConnection, route_handler: BaseRouteHandler):
    request_header = connection.headers.get("X-API-KEY", False)
    if not request_header:
        raise NotAuthorizedException()

    if not await APIToken.validate_token_is_valid(request_header):
        raise NotAuthorizedException()
