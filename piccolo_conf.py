from piccolo.engine.postgres import PostgresEngine

from piccolo.conf.apps import AppRegistry


DB = PostgresEngine(
    config={
        "database": "piccolo_project",
        "user": "postgres",
        "password": "",
        "host": "localhost",
        "port": 5432,
    }
)

APP_REGISTRY = AppRegistry(apps=["bot.piccolo_app", "piccolo_admin.piccolo_app"])
