#!/usr/bin/env bash

# shellcheck disable=SC2086
#uv run saq shared.saq.worker.SAQ_SETTINGS $EXTRA_ARGS
uv run litestar --app app:app workers run