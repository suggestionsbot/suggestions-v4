from pathlib import Path

from piccolo.conf.apps import AppConfig, table_finder

APP_CONFIG = AppConfig(
    app_name="bot",
    migrations_folder_path=Path(__file__).resolve() / "piccolo_migrations",
    table_classes=table_finder(modules=["bot.tables"], exclude_imported=False),
    migration_dependencies=[],
    commands=[],
)
