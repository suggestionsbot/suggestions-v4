Migration execution order:
1. Apache Hop: `load_user_configs.hpl` - Roughly a minute or two
2. Apache Hop: `load_guild_configs.hpl` - Roughly a minute or two
3. Python: `ensure_configs_exist.py` - Roughly five minutes
   - Note: Ensure indexes exist on the Mongo collections

