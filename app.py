import os

import jinja2
from dotenv import load_dotenv
from litestar import Litestar, asgi, Request
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.contrib.opentelemetry import OpenTelemetryPlugin, OpenTelemetryConfig
from litestar.datastructures import ResponseHeader, State
from litestar.exceptions import NotFoundException
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import (
    ScalarRenderPlugin,
)
from litestar.openapi.spec import SecurityScheme, Components
from litestar.plugins.flash import FlashPlugin, FlashConfig
from litestar.static_files import StaticFilesConfig
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from litestar.template import TemplateConfig
from litestar.types import Receive, Scope, Send, Empty
from opentelemetry import trace
from piccolo.engine import engine_finder
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from web import constants
from web.admin_portal import configure_piccolo_admin
from web.constants import IS_PRODUCTION
from web.controllers import AuthController, DebugController
from web.controllers.api import APIAlertController, APIAuthTokenController
from web.endpoints import (
    home,
)
from web.exception_handlers import (
    redirect_for_auth,
    RedirectForAuth,
    handle_500,
    handle_404,
)
from web.middleware import EnsureAuth
from web.tables import (
    APIToken,
    Users,
)
from web.util.flash import inject_alerts
from web.controllers import OAuthController

load_dotenv()


@asgi("/admin/", is_mount=True, copy_scope=True)
async def admin(scope: "Scope", receive: "Receive", send: "Send") -> None:
    request = Request(scope, receive, send)
    await EnsureAuth.get_user_from_connection(request, possible_redirect="/admin/")
    await configure_piccolo_admin()(scope, receive, send)


async def open_database_connection_pool():
    try:
        engine = engine_finder()
        await engine.start_connection_pool()
    except Exception:
        print("Unable to connect to the database")


async def close_database_connection_pool():
    try:
        engine = engine_finder()
        await engine.close_connection_pool()
    except Exception:
        print("Unable to connect to the database")


async def before_request(request: Request) -> dict[str, str] | None:
    await inject_alerts_on_ui_view(request)
    await inject_user_into_trace(request)
    return None


async def inject_user_into_trace(
    request: Request[Users, APIToken | None, State],
) -> None:
    if "user" not in request.scope or ("user" in request.scope and not request.user):
        # No user on request
        return None

    current_span = trace.get_current_span()
    if not current_span:
        return None

    current_span.set_attribute("user.id", request.user.id)
    current_span.set_attribute("user.email", request.user.email)

    if "auth" in request.scope and isinstance(request.scope["auth"], APIToken):
        current_span.set_attribute("user.api_token.id", request.auth.id)  # type: ignore

    return None


async def inject_alerts_on_ui_view(request: Request) -> dict[str, str] | None:
    if "user" not in request.scope:
        # Try to ensure we always have a user present
        # even if the route doesn't explicitly want one
        if "X-API-KEY" in request.headers:
            raw_token = request.headers["X-API-KEY"]
            if await APIToken.validate_token_is_valid(raw_token):
                api_token = await APIToken.get_instance_from_token(raw_token)
                request.scope["user"] = api_token.user
                request.scope["auth"] = api_token

        else:
            user = await EnsureAuth.get_user_from_connection(
                request, fail_on_not_set=False
            )
            request.scope["user"] = user

    if "user" in request.scope and request.scope["user"] is not None:
        # We have an authed user
        if "auth" in request.scope and isinstance(request.scope["auth"], APIToken):
            # It's an API client, no point in showing alerts
            pass
        else:
            await inject_alerts(request, request.scope["user"])

    return None


logging_config = None
if constants.IS_PRODUCTION:
    constants.configure_otel()

elif constants.ENFORCE_OTEL:
    constants.configure_otel()

else:
    # Just print logs locally during dev
    logging_config = Empty

open_telemetry_config = OpenTelemetryConfig()
cors_config = CORSConfig(
    allow_origins=[],
    allow_headers=[],
    allow_methods=[],
    allow_credentials=False,
)
csrf_config = CSRFConfig(
    secret=constants.CSRF_TOKEN,
    # Aptly named so it doesnt clash
    # with piccolo 'csrftoken' cookies
    cookie_name="csrf_token",
    cookie_secure=True,
    cookie_httponly=True,
    # Exclude routes Piccolo handles itself
    exclude=[
        "/admin/",
        "/auth",
        # It's manged via Tokens not cookies so is fine
        "/api",
    ],
)
# noinspection PyTypeChecker
rate_limit_config = RateLimitConfig(
    rate_limit=("second", 10),
    exclude=[
        "/docs",
        "/admin/",
        "/api",
    ],
)
ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        searchpath=[
            os.path.join(os.path.dirname(__file__), "web", "templates"),
        ]
    ),
    autoescape=True,
)
template_config = TemplateConfig(
    directory="web/templates",
    engine=JinjaTemplateEngine.from_environment(ENVIRONMENT),
)
flash_plugin = FlashPlugin(
    config=FlashConfig(template_config=template_config),
)
session_config = CookieBackendConfig(secret=constants.SESSION_KEY)
exception_handlers: dict[..., ...] = {
    RedirectForAuth: redirect_for_auth,
    NotFoundException: handle_404,
}
if IS_PRODUCTION:
    exception_handlers[HTTP_500_INTERNAL_SERVER_ERROR] = handle_500

routes = [
    admin,
    home,
    AuthController,
    APIAlertController,
    APIAuthTokenController,
    OAuthController,
]
if not constants.IS_PRODUCTION:
    routes.append(DebugController)

middleware = [
    rate_limit_config.middleware,
    session_config.middleware,
]
if constants.TRUSTED_PROXIES:
    middleware.append(ProxyHeadersMiddleware)

app = Litestar(
    route_handlers=routes,
    template_config=template_config,
    static_files_config=[
        StaticFilesConfig(directories=["static"], path="/static/"),
    ],
    on_startup=[open_database_connection_pool],
    on_shutdown=[close_database_connection_pool],
    debug=not IS_PRODUCTION,
    openapi_config=OpenAPIConfig(
        title=constants.SITE_NAME.rstrip() + " API",
        version="0.0.0",
        render_plugins=[
            ScalarRenderPlugin(
                options={
                    "hideClientButton": True,
                    "showSidebar": True,
                    "showToolbar": "never",
                    "operationTitleSource": "summary",
                    "theme": "default",
                    "persistAuth": False,
                    "telemetry": False,
                    "layout": "modern",
                    "isEditable": False,
                    "isLoading": False,
                    "hideModels": False,
                    "documentDownloadType": "both",
                    "hideTestRequestButton": False,
                    "hideSearch": False,
                    "showOperationId": False,
                    "hideDarkModeToggle": False,
                    "withDefaultFonts": True,
                    "defaultOpenAllTags": False,
                    "expandAllModelSections": False,
                    "expandAllResponses": False,
                    "orderSchemaPropertiesBy": "alpha",
                    "orderRequiredPropertiesFirst": True,
                    "_integration": "html",
                    "default": False,
                }
            )
        ],
        path="/docs",
        components=Components(
            security_schemes={
                "session": SecurityScheme(
                    type="apiKey",
                    name="id",
                    security_scheme_in="cookie",
                    description="Session based authentication.",
                ),
                "adminSession": SecurityScheme(
                    type="apiKey",
                    name="id",
                    security_scheme_in="cookie",
                    description="An Admin users session.",
                ),
                "apiKey": SecurityScheme(
                    type="apiKey",
                    name="X-API-KEY",
                    security_scheme_in="header",
                    description="A valid API token.",
                ),
            }
        ),
    ),
    cors_config=cors_config,
    csrf_config=csrf_config,
    logging_config=logging_config,
    middleware=middleware,
    plugins=[flash_plugin, OpenTelemetryPlugin(open_telemetry_config)],
    response_headers=[
        ResponseHeader(
            name="x-frame-options",
            value="SAMEORIGIN",
            description="Security header",
        ),
        ResponseHeader(
            name="x-content-type-options",
            value="nosniff",
            description="Security header",
        ),
        ResponseHeader(
            name="referrer-policy",
            value="strict-origin",
            description="Security header",
        ),
        ResponseHeader(
            name="permissions-policy",
            value="microphone=(); geolocation=(); fullscreen=();",
            description="Security header",
        ),
        ResponseHeader(
            name="content-security-policy",
            value="default-src 'none'; frame-ancestors 'none'; object-src 'none';"
            " base-uri 'none'; script-src 'nonce-{}' 'strict-dynamic'; style-src "
            "'nonce-{}' 'strict-dynamic'; require-trusted-types-for 'script'",
            description="Security header",
            documentation_only=True,
        ),
    ],
    exception_handlers=exception_handlers,
    before_request=before_request,
)
