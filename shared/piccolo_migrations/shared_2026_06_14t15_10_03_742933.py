from piccolo.apps.migrations.auto.migration_manager import MigrationManager

from shared.tables import Suggestions

ID = "2026-06-14T15:10:03:742933"
VERSION = "1.34.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(migration_id=ID, app_name="", description=DESCRIPTION)

    async def run():
        q = "alter table suggestion_votes add constraint unique_votes UNIQUE (user_id, suggestion)"
        await Suggestions.raw(q)

    manager.add_raw(run)
    return manager
