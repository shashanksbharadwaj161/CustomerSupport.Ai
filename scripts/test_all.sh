#!/usr/bin/env bash
# Everything that can be verified on this machine, without spending money (fake LLM, local models).
#   scripts/test_all.sh            # unit tests + web build + UI E2E + a11y + call E2E (needs Chromium + CPU models)
#   QUICK=1 scripts/test_all.sh    # unit tests + web typecheck only
#   INDIC=1 scripts/test_all.sh    # also Hindi/Bengali/Kannada live calls with real FLEURS speech (slow, CPU)
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-}"; [ -z "$PY" ] && { [ -x .venv/bin/python ] && PY=.venv/bin/python || PY=python3; }
fail=0
step() { echo; echo "=== $*"; }
step "unit + integration tests (pytest)"; "$PY" -m pytest -q tests || fail=1
step "web typecheck"; (cd web && npx tsc --noEmit) || fail=1
[ -n "${QUICK:-}" ] && exit $fail
step "web build"; (cd web && npm run build >/dev/null) || fail=1
export SHAON_DATA_DIR="$(mktemp -d)" SHAON_LLM_PROVIDER=fake SHAON_PRELOAD="stt:en,tts:en,tts:ja" SHAON_SELF_URL="http://127.0.0.1:8766"
"$PY" -m uvicorn --factory api.main:create_app --port 8766 --log-level warning > "$SHAON_DATA_DIR/server.log" 2>&1 &
SERVER=$!; trap 'kill $SERVER 2>/dev/null' EXIT
for i in $(seq 1 60); do curl -sf localhost:8766/api/health >/dev/null && break; sleep 1; done
step "demo seeding (two demo agents get their sites)"
for i in $(seq 1 60); do n=$(curl -s localhost:8766/api/knowledge | "$PY" -c "import json,sys; print(sum(s['status']=='ready' for s in json.load(sys.stdin)))"); [ "$n" = "2" ] && break; sleep 2; done
[ "$n" = "2" ] && echo "seeded: 2 ready sources" || { echo "seeding FAILED ($n ready)"; fail=1; }
step "UI E2E"; (cd web && node scripts/ui_e2e.mjs http://127.0.0.1:8766) || fail=1
step "accessibility (axe)"; (cd web && node scripts/a11y.mjs http://127.0.0.1:8766 >/dev/null && echo "0 violations") || fail=1
kill $SERVER 2>/dev/null; trap - EXIT
step "call E2E (fake mic -> STT -> fake LLM -> TTS -> browser)"
CASES="en_question:smallwebrtc:off en_question:websocket:off ja_question:websocket:off" tests/e2e/run_e2e.sh || fail=1
if [ -n "${INDIC:-}" ]; then  # opt-in: real FLEURS speech for hi/bn/kn + switches (slow on CPU; loads MMS ~4 GB)
  step "Indic live-call E2E (FLEURS caller audio, CPU engines)"
  "$PY" tests/e2e/run_indic_e2e.py || fail=1
fi
step "exposed (tunnel) mode: password login + token on the WebSocket upgrade"
SHAON_DATA_DIR="$(mktemp -d)" SHAON_EXPOSED=1 ALLOW_KEY_EDIT=false ADMIN_PASSWORD=test-password-123 SHAON_SEED_DEMO=0 \
  SHAON_PRELOAD="stt:en,tts:en" "$PY" -m uvicorn --factory api.main:create_app --port 8767 --log-level warning > /dev/null 2>&1 &
EXP=$!; trap 'kill $EXP 2>/dev/null' EXIT
for i in $(seq 1 60); do curl -sf localhost:8767/api/health >/dev/null && break; sleep 1; done; sleep 15
code=$(curl -s -o /dev/null -w "%{http_code}" localhost:8767/api/settings); [ "$code" = 401 ] && echo "API without token: 401 (ok)" || { echo "API without token: $code"; fail=1; }
(cd web && LOGIN_PASSWORD=test-password-123 node scripts/call_e2e.mjs http://127.0.0.1:8767 "$(realpath ../tests/e2e/audio/en_question.wav)" websocket off saturday "test model reply" > /dev/null) \
  && echo "WebSocket call after login: OK" || { echo "WebSocket call after login: FAIL"; fail=1; }
kill $EXP 2>/dev/null; trap - EXIT
echo; [ $fail = 0 ] && echo "ALL PASSED" || echo "SOME CHECKS FAILED"
exit $fail
