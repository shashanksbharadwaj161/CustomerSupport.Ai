#!/usr/bin/env bash
# Browser E2E matrix with the fake LLM (no API spend): fake mic -> real STT/TTS on this machine.
# Writes tests/e2e/results/*.json. Needs: python deps [app,stt-whisper,tts-kokoro], web build, Playwright Chromium.
#   tests/e2e/run_e2e.sh                 # en over both transports, effects off/lite/full
#   CASES="ja_question:websocket:off" tests/e2e/run_e2e.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
PY="${PYTHON:-python3}"; [ -d .venv ] && PY=".venv/bin/python"
OUT=tests/e2e/results; AUDIO=${AUDIO_DIR:-tests/e2e/audio}
mkdir -p "$OUT"
[ -f "$AUDIO/en_question.wav" ] || "$PY" tests/e2e/make_fake_mic.py "$AUDIO"
export SHAON_DATA_DIR="${SHAON_DATA_DIR:-$(mktemp -d)}" SHAON_LLM_PROVIDER=fake SHAON_PRELOAD="stt:en,tts:en,tts:ja"
"$PY" -m uvicorn --factory api.main:create_app --port 8765 --log-level warning > "$OUT/server.log" 2>&1 &
SERVER=$!; trap 'kill $SERVER 2>/dev/null' EXIT
for i in $(seq 1 60); do curl -sf localhost:8765/api/health >/dev/null && break; sleep 2; done
sleep 15  # let the preload finish
CASES="${CASES:-en_question:smallwebrtc:off en_question:websocket:off en_question:websocket:lite en_question:websocket:full}"
fail=0
for c in $CASES; do
  IFS=: read -r wav transport effects <<< "$c"
  case $wav in en_*) U="saturday"; A="test model reply";; ja_*) U="土曜|支店"; A="テスト用";; esac
  (cd web && node scripts/call_e2e.mjs http://127.0.0.1:8765 "$PWD/../$AUDIO/$wav.wav" "$transport" "$effects" "$U" "$A") > "$OUT/$wav-$transport-$effects.json" 2>&1 || fail=1
  python3 -c "import json;d=json.load(open('$OUT/$wav-$transport-$effects.json'));t=(d.get('turns') or [{}])[0];print('$c', 'OK' if d['ok'] else 'FAIL', 'first_audio_ms', t.get('first_audio_ms'))" || fail=1
done
exit $fail
