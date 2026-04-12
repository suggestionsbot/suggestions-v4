Migration execution order:
1. Migrate shared, make migration for bot, migrate bot, drop vote indexes
2. Apache Hop: `load_user_configs.hpl` - Roughly a minute (Up to ten if the DB is full. Index issue?)
3. Apache Hop: `load_guild_configs.hpl` - Roughly a couple minutes
4. Python: `ensure_configs_exist.py` - Roughly five minutes
   - Note: Ensure indexes exist on the Mongo collections for `suggestion_author_id` and `guild_id`
5. Python: `migrate_queued_suggestions.py` - Roughly a minute
6. Python: `migrate_suggestions.py` - Roughly ten minutes for suggestions
7. Using Pycharm export the `suggestions` table to JSON `suggestions.json` - Couple minutes roughly
8. Python: `build_related_suggestions.py` - roughly 25 minutes
9. Python: `migrate_votes.py`
10. Use psql to import
    - `psql -h localhost -p 2501 -U suggestions_db_user -W -d suggestions_db -c "\copy suggestion_votes (created_at, last_modified_at, suggestion, user_id, vote_type)
from '/home/skelmis/Code/Suggestions/suggestions_version_4/migrations/votes.csv'
with (FORMAT csv)"` - roughly 5-7 minutes
11. Recreate indexes

```sql
\copy suggestion_votes (created_at, last_modified_at, suggestion, user_id, vote_type)
from '/home/skelmis/Code/Suggestions/suggestions_version_4/migrations/votes.csv'
with (FORMAT csv)
```