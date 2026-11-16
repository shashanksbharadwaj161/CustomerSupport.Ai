# STATUS

Honest state of every milestone. VERIFIED = run and checked in this repo's tests or by a measured run.
PENDING = cannot be done here; says who must do it.

## D0 - Design spike: BUILT
- Built: Next.js 16 static export in `web/`, single tokens file `web/src/styles/tokens.css` (JS reads it back via `lib/tokens.ts`), self-hosted Noto fonts for all 5 scripts, effects tiers Auto/Full/Lite/Off + `prefers-reduced-motion` + pause when hidden (`lib/effects.tsx`), the Signal (R3F particles, 7 states, 5 language motifs, AnalyserNode-driven) with a static fallback, GPU ASCII post-process (Latin glyphs only), landing hero with the wordmark assembling from particles, Signal lab page.
- Verified: build + typecheck; screenshots in `design/screens/` for full/lite/off on desktop and phone; lab page frame rate in this VM (software WebGL, no GPU): full 48 fps, lite/off 60 fps (lite is capped to 30 fps rendering by design; page rAF stays 60).
- PENDING (user): moodboard, reference inventory and assets in `design/` for the final styling pass. Tokens are provisional.

## M1 - Voice skeleton: BUILT + VERIFIED (English, CPU)
- Built: FastAPI app serving UI + API + voice worker on one port (`scripts/start.sh`); Pipecat 1.16 pipeline
  transport -> Silero VAD -> router STT (LID + per-language engine) -> brain (TurnEngine) -> router TTS (voice by reply script) -> transport;
  transport chosen by config (`TRANSPORT=both|smallwebrtc|websocket`): SmallWebRTC and a raw-PCM WebSocket transport;
  pluggable LLM provider (Anthropic Haiku 5.5 with prompt caching + spend recording; Fake for tests; Demo when no key);
  Settings page: API key stored encrypted (Fernet, `data/secret.key` mode 0600), DB key wins over `.env`, never returned (last 4),
  Test key button, `ALLOW_KEY_EDIT`, admin password, key scrubbed from logs/errors/transcripts; spend cap + spend in DB;
  honest demo-mode banner; per-turn latency (STT, LID, LLM first text, guard, TTS, first audio) stored per turn and shown live.
- Verified in this VM: 37 unit tests; browser E2E (Chromium fake mic with a Kokoro-generated question) passes on BOTH transports:
  Whisper small transcribed "What time does your branch open on Saturday?" exactly; fake LLM reply spoken by Kokoro and received by the browser.
  Time-to-first-audio with/without effects measured: design/perf.md (CPU-only VM: 3.9 s effects off, 5.2-6.0 s lite, 21-29 s full).
- NOT verified: real Claude replies (no key in this session, by rule). PENDING (user): add key in Settings, press Test key.
