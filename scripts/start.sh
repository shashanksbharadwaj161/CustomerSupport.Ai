#!/usr/bin/env bash
# One command: build the web UI (if needed) and serve UI + API + voice worker on one port.
#   scripts/start.sh              # http://localhost:8000
#   PORT=8080 scripts/start.sh
#   SHAON_LLM_PROVIDER=fake scripts/start.sh   # scripted LLM, no API key (banner says so)
# Runs in honest demo mode when the API key or speech models are missing (see the banner and Settings).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PY="${PYTHON:-python3}"
[ -d .venv ] && PY=".venv/bin/python"

if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example (no secrets in it yet)."; fi

if [ ! -d web/out ] || [ -n "${REBUILD_WEB:-}" ] || [ "$(find web/src -newer web/out -print -quit 2>/dev/null)" ]; then
  echo "Building web UI..."
  (cd web && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build >/dev/null)
fi

export SHAON_PRELOAD="${SHAON_PRELOAD:-stt:en,tts:en}"
echo "ShaOn on http://$HOST:$PORT  (API docs: /api/docs)"
exec "$PY" -m uvicorn --factory api.main:create_app --host "$HOST" --port "$PORT" --log-level "${LOG_LEVEL:-warning}"
