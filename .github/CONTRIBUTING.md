# How to contribute

1. Fork the repository
2. Make changes
3. Create a pull request

### Commits

Try to use <https://scopedcommits.com/>. Examples include:
- `/suggest: Change base permissions`
- `migrations: reset to one per subsystem`
- `utility(bot): change helper script to be tz aware`

### Before PR

Run and resolve the following commands on changes:
- `uv run black .`
- `uv run pytest .` (TBD not working)
- `uv run ty check .`
- `uv run ruff check .`
