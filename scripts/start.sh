#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -d dist || { echo 'Run npm run build first.' >&2; exit 1; }
if [ -f .env ]; then
  set -- --env-file .env
else
  set --
fi
exec .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
