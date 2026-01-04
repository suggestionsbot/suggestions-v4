import os

from piccolo.conf.apps import AppConfig, table_finder


CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))


APP_CONFIG = AppConfig(
    app_name="web",
    migrations_folder_path=os.path.join(CURRENT_DIRECTORY, "piccolo_migrations"),
    table_classes=table_finder(modules=["web.tables"], exclude_imported=False),
    migration_dependencies=[],
    commands=[],
)
