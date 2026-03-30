Migration execution order:
1. Apache Hop: `load_user_configs.hpl` - Roughly a minute (Up to ten if the DB is full. Index issue?)
2. Apache Hop: `load_guild_configs.hpl` - Roughly a couple minutes
3. Python: `ensure_configs_exist.py` - Roughly five minutes
   - Note: Ensure indexes exist on the Mongo collections for `suggestion_author_id` and `guild_id`
4. Python: `migrate_queued_suggestions.py` - Roughly a minute
5. Python: `migrate_suggestions.py` - Roughly ten minutes for suggestions, an hour for votes

TODO: Once `Suggestions` are migrated, set the `related_suggestion` field on `QueuedSuggestions`