#!/usr/bin/env bash
# Everything that can be verified on this machine, without spending money (fake LLM, local models).
#   scripts/test_all.sh            # unit tests + web build + UI E2E + a11y + call E2E (needs Chromium + CPU models)
#   QUICK=1 scripts/test_all.sh    # unit tests + web typecheck only
#   INDIC=1 scripts/test_all.sh    # also 5-language live calls + switches with real FLEURS speech in share mode (slow, CPU)
#   PWSH=/path/to/pwsh             # run the Windows launcher test under PowerShell 7 (auto if pwsh is on PATH)
#   INSTALLER=1 scripts/test_all.sh  # also the Windows installer scenarios (pwsh + stubbed winget/git/pip/npm, ~2 min)
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
step "settings UI on local preview (no login, fake key masked, model persists, cap, orb states; no Anthropic call)"
"$PY" tests/e2e/run_settings_e2e.py || fail=1
step "share mode visitor UI (wrong passcode, Get-ready, busy, call time limit, host offline)"
"$PY" tests/e2e/run_share_ui_e2e.py || fail=1
PWSH="${PWSH:-$(command -v pwsh || true)}"
if [ -n "$PWSH" ]; then
  step "share launcher (scripts/share.ps1 under pwsh, stub tunnel: link, drop + new link, cleanup)"
  "$PY" tests/share/run_launcher_test.py "$PWSH" || fail=1
  step "local preview launcher (scripts/local.ps1: no passcode despite stale env, Settings editable, loopback only)"
  PYTHON="$PY" "$PY" tests/share/run_local_test.py "$PWSH" || fail=1
else
  echo; echo "=== share launcher: SKIPPED (pwsh not installed; set PWSH=/path/to/pwsh)"
fi
if [ -n "${INSTALLER:-}" ]; then  # opt-in: scripts/install.ps1 scenarios (fresh, partial, second run, resume, low disk, private repo)
  if [ -n "$PWSH" ]; then
    step "Windows installer (scripts/install.ps1 under pwsh, stubbed winget / git clone / pip / npm / cloudflared)"
    PWSH="$PWSH" PYTHON="$PY" "$PY" tests/install/run_installer_test.py || fail=1
  else
    echo; echo "=== Windows installer: SKIPPED (pwsh not installed; set PWSH=/path/to/pwsh)"
  fi
fi
if [ -n "${INDIC:-}" ]; then  # opt-in: 5 languages + 3 switches with real FLEURS speech, in SHARE mode (slow on CPU; MMS ~4 GB)
  step "live calls en/ja/hi/bn/kn + switches through share mode (FLEURS caller audio, CPU engines)"
  SHARE=1 "$PY" tests/e2e/run_indic_e2e.py || fail=1
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
