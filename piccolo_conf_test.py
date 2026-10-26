import os

from dotenv import load_dotenv
from piccolo.conf.apps import AppRegistry
from piccolo.engine import PostgresEngine

load_dotenv()

# Under pytest-xdist each worker (gw0, gw1, ...) gets its own database, since
# every test drops and recreates all tables.
_XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER")

DB = PostgresEngine(
    config={
        "database": f"tests_{_XDIST_WORKER}" if _XDIST_WORKER else "tests",
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.environ["POSTGRES_PORT"]),
    },
)
APP_REGISTRY = AppRegistry(
    apps=[
        "bot.piccolo_app",
        "shared.piccolo_app",
        "web.piccolo_app",
        "piccolo_admin.piccolo_app",
        "piccolo_api.mfa.authenticator.piccolo_app",
    ]
)
