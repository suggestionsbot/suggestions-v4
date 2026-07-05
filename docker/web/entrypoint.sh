#!/usr/bin/env bash

EXPOSED_PORT="${PORT:-2200}"
/code/migrate.sh
uv run uvicorn app:app --proxy-headers --host 0.0.0.0 --port "$EXPOSED_PORT" --forwarded-allow-ips="*" --no-server-header