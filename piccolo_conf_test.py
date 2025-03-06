from piccolo.engine.sqlite import SQLiteEngine
from piccolo.conf.apps import AppRegistry

DB = SQLiteEngine("testing.db")
APP_REGISTRY = AppRegistry(apps=["bot.piccolo_app", "piccolo_admin.piccolo_app"])
