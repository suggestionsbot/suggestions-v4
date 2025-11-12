from dotenv import load_dotenv
from piccolo.conf.apps import AppRegistry
from piccolo.engine import PostgresEngine

from bot.constants import INFISICAL_SDK

load_dotenv()

DB = PostgresEngine(
    config={
        "database": INFISICAL_SDK.get_secret("POSTGRES_DB"),
        "user": INFISICAL_SDK.get_secret("POSTGRES_USER"),
        "password": INFISICAL_SDK.get_secret("POSTGRES_PASSWORD"),
        "host": INFISICAL_SDK.get_secret("POSTGRES_HOST"),
        "port": int(INFISICAL_SDK.get_secret("POSTGRES_PORT")),
    },
)
APP_REGISTRY = AppRegistry(
    apps=[
        "bot.piccolo_app",
        "shared.piccolo_app",
    ]
)
