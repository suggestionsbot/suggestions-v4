import logging
import os
import re
from datetime import timedelta
from typing import Literal, cast

from commons import value_to_bool
from dotenv import load_dotenv
from infisical_sdk import InfisicalSDKClient
from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics._internal.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    Resource,
    DEPLOYMENT_ENVIRONMENT,
    HOST_NAME,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from piccolo_api.encryption.providers import XChaCha20Provider
from piccolo_api.mfa.authenticator.provider import AuthenticatorProvider

load_dotenv()
infisical_client = InfisicalSDKClient(host="https://secrets.skelmis.co.nz")
infisical_client.auth.universal_auth.login(
    client_id=os.environ["INFISICAL_ID"],
    client_secret=os.environ["INFISICAL_SECRET"],
)


def configure_otel():
    host = get_secret("OTEL_HOST", infisical_client)
    endpoint = get_secret("OTEL_ENDPOINT", infisical_client)
    bearer_token = get_secret("OTEL_BEARER", infisical_client)
    service_name = get_secret("OTEL_SERVICE_NAME", infisical_client)
    deployment_environment: Literal["Production", "Development", "Staging"] = cast(
        Literal["Production", "Development", "Staging"],
        get_secret("OTEL_DEPLOYMENT_ENVIRONMENT", infisical_client),
    )
    headers = {"Authorization": f"Bearer {bearer_token}"}
    attributes = {
        SERVICE_NAME: service_name,
        DEPLOYMENT_ENVIRONMENT: deployment_environment,
        HOST_NAME: host,
    }
    resource = Resource.create(attributes=attributes)

    # Setup TracerProvider for trace correlation
    trace_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(trace_provider)
    trace_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers)
        )
    )

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics", headers=headers)
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # Configure logger provider
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    # Add OTLP exporter (reads endpoint/headers from environment variables)
    exporter = OTLPLogExporter(endpoint=f"{endpoint}/v1/logs", headers=headers)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    # Attach OTel handler to Python's root logger
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def get_secret(secret_name: str, infisical_client: InfisicalSDKClient) -> str:
    return infisical_client.secrets.get_secret_by_name(
        secret_name=secret_name,
        project_id=os.environ["INFISICAL_PROJECT_ID"],
        environment_slug=os.environ["INFISICAL_SLUG"],
        secret_path="/",
        view_secret_value=True,
    ).secretValue


SITE_NAME: str = os.environ.get("SITE_NAME", "Template Website")
"""The site name for usage in templates etc"""

IS_PRODUCTION: bool = not value_to_bool(os.environ.get("DEBUG"))
"""Are we in production?"""

ENFORCE_OTEL: bool = value_to_bool(os.environ.get("ENFORCE_OTEL"))
"""Force OTEL usage, good for local debugging."""

ALLOW_REGISTRATION: bool = value_to_bool(os.environ.get("ALLOW_REGISTRATION", True))
"""Whether users should be allowed to create new accounts."""

SERVING_DOMAIN: list[str] = os.environ.get("SERVING_DOMAIN", "localhost").split(",")
"""The domain this site will run on. Used for cookies etc."""

CHECK_PASSWORD_AGAINST_HIBP: bool = not value_to_bool(
    os.environ.get("DISABLE_HIBP", False)
)
"""If True, checks passwords against Have I Been Pwned"""

SIMPLE_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
"""A simple email regex. Not perfect, but good enough."""

MAKE_FIRST_USER_ADMIN: bool = value_to_bool(
    os.environ.get("MAKE_FIRST_USER_ADMIN", True)
)
"""Makes the first user to sign in admin. Just makes life easier."""

REQUIRE_MFA: bool = value_to_bool(os.environ.get("REQUIRE_MFA", False))
"""Enforces the usage of MFA for authentication.

Due to platform limitations, it won't be enforced if users
only sign in via the admin portal.
"""

DONT_SEND_EMAILS: bool = value_to_bool(os.environ.get("DONT_SEND_EMAILS", False))
"""If True, prints emails to console instead of sending them"""

MAGIC_LINK_VALIDITY_WINDOW = timedelta(minutes=5)
"""How long since it is sent can a link be used to authenticate"""

HAS_IMPLEMENTED_OAUTH = value_to_bool(os.environ.get("HAS_IMPLEMENTED_OAUTH", False))
"""Set to True if `oauth_controller.py` has been setup and configured to work."""

TRUSTED_PROXIES = value_to_bool(os.environ.get("TRUSTED_PROXIES", False))
"""Trust proxy headers"""

HAS_IMPLEMENTED_MAGIC_LINK = value_to_bool(
    os.environ.get("HAS_IMPLEMENTED_MAGIC_LINK", False)
)
"""Set to True if emails are configured to work."""

# CloudFlare Turnstile configuration items
CF_TURNSTILE_SITE_KEY = None
CF_TURNSTILE_SECRET_KEY = None
USE_CF_TURNSTILE = value_to_bool(os.environ.get("USE_CF_TURNSTILE", False))
if USE_CF_TURNSTILE:
    CF_TURNSTILE_SITE_KEY = get_secret("CF_TURNSTILE_SITE_KEY", infisical_client)
    CF_TURNSTILE_SECRET_KEY = get_secret("CF_TURNSTILE_SECRET_KEY", infisical_client)

SESSION_KEY = bytes.fromhex(get_secret("SESSION_KEY", infisical_client))
CSRF_TOKEN = get_secret("CSRF_TOKEN", infisical_client)
ENCRYPTION_KEY = bytes.fromhex(get_secret("ENCRYPTION_KEY", infisical_client))
ENCRYPTION_PROVIDER = XChaCha20Provider(ENCRYPTION_KEY)
MFA_TOTP_PROVIDER = AuthenticatorProvider(
    ENCRYPTION_PROVIDER, issuer_name=SITE_NAME, valid_window=1
)
MAILGUN_API_KEY = get_secret("MAILGUN_API_KEY", infisical_client)
