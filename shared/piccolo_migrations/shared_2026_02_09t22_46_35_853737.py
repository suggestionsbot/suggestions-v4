from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-02-09T22:46:35:853737"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_table(
        old_class_name="SuggestionsVotes",
        old_tablename="suggestions_votes",
        new_class_name="SuggestionVotes",
        new_tablename="suggestion_votes",
        schema=None,
    )

    return manager
