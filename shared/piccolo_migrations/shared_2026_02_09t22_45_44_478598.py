from piccolo.apps.migrations.auto.migration_manager import MigrationManager


ID = "2026-02-09T22:45:44:478598"
VERSION = "1.30.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="shared", description=DESCRIPTION
    )

    manager.rename_table(
        old_class_name="SuggestionsVote",
        old_tablename="suggestions_vote",
        new_class_name="SuggestionsVotes",
        new_tablename="suggestions_votes",
        schema=None,
    )

    return manager
