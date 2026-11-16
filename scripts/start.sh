#!/usr/bin/env bash
# One command: check, build the web UI if needed, then serve UI + API + voice worker on ONE port.
#   scripts/start.sh                            # http://127.0.0.1:8000
#   PORT=8080 scripts/start.sh
#   HOST=0.0.0.0 scripts/start.sh               # LAN (set ADMIN_PASSWORD first!)
#   SHAON_LLM_PROVIDER=fake scripts/start.sh    # scripted LLM, no API key (the banner says so)
# Missing key or models => honest demo mode (banner + Settings > Engines). Run scripts/doctor.py for a checklist.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
fi

if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example (contains no secrets)."; fi

if ! "$PY" -c "import fastapi, pipecat, cryptography" 2>/dev/null; then
  echo "Python deps missing for $PY. Install:  $PY -m pip install -e '.[app,stt-whisper,tts-kokoro,dev]'" >&2
  exit 1
fi
if [ "$HOST" != "127.0.0.1" ] && [ "$HOST" != "localhost" ] && ! grep -q '^ADMIN_PASSWORD=..*' .env && [ -z "${ADMIN_PASSWORD:-}" ]; then
  echo "Refusing to listen on $HOST without ADMIN_PASSWORD (set it in .env)." >&2
  exit 1
fi
if command -v ss >/dev/null && ss -ltn "( sport = :$PORT )" | grep -q LISTEN; then
  echo "Port $PORT is already in use. Use PORT=xxxx scripts/start.sh" >&2
  exit 1
fi

if [ ! -f web/out/index.html ] || [ -n "${REBUILD_WEB:-}" ] || [ -n "$(find web/src web/public -newer web/out/index.html -print -quit 2>/dev/null)" ]; then
  echo "Building web UI (first run takes a minute)..."
  (cd web && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build >/dev/null)
fi

export SHAON_PRELOAD="${SHAON_PRELOAD:-stt:en,tts:en}"
export SHAON_SELF_URL="${SHAON_SELF_URL:-http://127.0.0.1:$PORT}"
echo "ShaOn Voice AI on http://$HOST:$PORT   (API docs /api/docs, checklist: $PY scripts/doctor.py)"
exec "$PY" -m uvicorn --factory api.main:create_app --host "$HOST" --port "$PORT" --log-level "${LOG_LEVEL:-warning}"
