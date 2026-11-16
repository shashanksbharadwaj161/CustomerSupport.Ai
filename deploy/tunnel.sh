#!/usr/bin/env bash
# $0 remote demo (DEPLOY.md): run ShaOn on THIS PC and expose it through a Cloudflare Quick Tunnel.
# Free, dev/testing grade: random URL, no uptime guarantee, ~200 in-flight requests, NO SSE (the UI polls instead).
#
#   ADMIN_PASSWORD='long-shared-password' deploy/tunnel.sh
#
# What it enforces: a password (the URL is public to anyone who has it), key editing locked (ALLOW_KEY_EDIT=false),
# crawler allowlist, WebSocket transport for remote browsers (the Live Call page picks it automatically off-localhost).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
[ -f .env ] && set -a && . ./.env && set +a
if [ -z "${ADMIN_PASSWORD:-}" ] || [ "${#ADMIN_PASSWORD}" -lt 12 ]; then
  echo "Set ADMIN_PASSWORD (12+ characters) in .env or the environment first. The tunnel URL is public." >&2; exit 1
fi
if ! command -v cloudflared >/dev/null; then
  cat >&2 <<'MSG'
cloudflared is not installed (free). Install it, then re-run:
  Linux/WSL2:  curl -L -o /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i /tmp/cloudflared.deb
  macOS:       brew install cloudflared
MSG
  exit 1
fi
export SHAON_EXPOSED=1 ALLOW_KEY_EDIT=false TRANSPORT=both
export CRAWL_ALLOWLIST="${CRAWL_ALLOWLIST:-127.0.0.1,localhost}"
LOG=$(mktemp)
PORT=$PORT scripts/start.sh > "$LOG" 2>&1 &
APP=$!
trap 'kill $APP 2>/dev/null' EXIT
for i in $(seq 1 90); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 1; done
curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null || { echo "app did not start:"; cat "$LOG"; exit 1; }
echo "App is up on http://127.0.0.1:$PORT. Starting the Quick Tunnel (Ctrl+C stops both)..."
echo "Then follow deploy/CHECKLIST.md (smoke test from a phone on mobile data, WebSocket call test)."
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"
