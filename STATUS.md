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

## M2 - Agent Studio core: BUILT + VERIFIED
- Built: profiles as one JSON document, a new version on every save, rollback = new version copying an old one; 5 presets
  (bank_support, tourism, ecommerce, clinic_frontdesk, custom) with persona, per-language greetings (AI disclosure enforced),
  politeness, style, guardrails, disclaimers, handoff per language, tool allowlist per type; server-side validation;
  prompt builder per profile (cached prefix) + live preview; Studio UI with 9 tabs and masked tab transitions;
  auth + rate-limit layer (`api/auth.py`): no-op locally, shared password + signed token when `ADMIN_PASSWORD` is set,
  WebSocket origin + token check, per-IP buckets for login / call start / crawl / preview.
- Verified: 49 unit tests (versioning, rollback, validation, tool allowlist, prompt contents, auth on protected routes);
  Playwright UI test edits, saves and rolls back an agent; screenshots in design/screens/.

## M3 - Languages: BUILT; VERIFIED for en + ja on CPU; hi/bn/kn PENDING
- Built: per-turn language ID (one Whisper pass gives probabilities + text), previous-language bias and threshold
  (`agent/engines.json` -> `lid`), dual recognition on low confidence (keeps the transcript whose script fits), script-flip,
  manual override from the Live Call page, per-language STT routing (IndicConformer for hi/bn/kn on GPU, Whisper fallback),
  reply language decided from the reply's script, per-language voice, per-language Sonnet override in Studio.
- Verified: 13 routing unit tests incl. 3 consecutive switch directions for 5 pairs (stub engines);
  browser E2E: Japanese call (Whisper small ja -> Kokoro ja) and an English -> Japanese switch inside ONE call
  (language and voice switched, first audio 3.9 s / 4.1 s on CPU); `run_switch` on synthetic Kokoro audio: en->ja PASS, ja->en PASS.
- Known: Whisper small heard 支店 as 視点 (homophone) - CPU model quality; GPU large-v3 expected better (measure in M0).
- PENDING (user): native recordings for all languages -> `python -m eval.runners.run_lid` (thresholds) and `run_switch`;
  hi/bn/kn speech output needs Indic Parler / OmniVoice on GPU (adapters complete, never run here).

## M4 - Knowledge: BUILT + VERIFIED
- Built: crawler with our own robots.txt check and clear user agent, same host + start-path scope, depth/page limits,
  query strings ignored, allowlist enforced when exposed; JS rendering via Crawl4AI (headless Chromium), Playwright fallback;
  cleaning (nav/footer/script removed, cross-page boilerplate dedupe), heading chunks with URL/title; BGE-M3 embeddings
  (lexical fallback clearly labelled when BGE-M3 is not downloaded) in Chroma (telemetry off), one collection per source;
  site brief by Claude (honestly skipped without a key); small sites go fully into the cached prompt; retrieval feeds each
  call turn with sources shown in the transcript; Knowledge page: drop zone, crawl graph, SSE progress with automatic
  polling fallback (`?mode=poll`, needed behind Quick Tunnels), pages, chunk preview, brief, test question, re-crawl, delete.
- Verified: 8 tests on two fake sites + a JS-rendered site served locally (robots skip, external links ignored, limits,
  dedupe, JS rendering via Crawl4AI, API ingest -> retrieve -> ask -> attach -> delete, SSE + polling, exposed allowlist);
  UI E2E crawls the demo site in SSE and polling modes. Cross-lingual retrieval through the real pipeline with BGE-M3
  (eval/results.md): hit@3 100% in en/ja/hi/bn/kn; hit@1 en 89%, ja 100%, hi 78%, bn 100%, kn 100%.
- PENDING (user): site brief needs the API key; real customer sites only with permission.

## M5 - Guardrails: BUILT; local layers VERIFIED; Claude layer PENDING (key)
- Built: layer 1 prompt rules; layer 2 local (free) input rules in en/hi/bn/kn/ja + romanized hi/bn (injection, prompt reveal,
  role override, other customers' / patients' data, bulk export, PIN/OTP/API-key requests, forbidden topics, human escalation,
  PII redaction with Luhn) and reply rules applied to EVERY sentence before TTS (prompt leak, 8+ digit runs, card/ID numbers,
  banned claims, forbidden topics unless refusing, English disclaimer append); layer 2 model: ONE combined Claude reply check
  (strict JSON, fails closed to the handoff), optional model input check (Studio toggle); layer 3 tool allowlist;
  every trigger logged per call (guardrail_events) and shown in the transcript.
- Verified: 55 guardrail tests (all 39 local-layer attacks caught; zero false positives on the 60 normal test lines;
  checker failure / invalid JSON / unknown verdict fail closed; streaming leak stopped mid-reply; blocked input never reaches the model).
  Red-team vs a worst-case always-complying fake model: 88% overall (100% of local-layer attacks, 45% of model-layer attacks).
- PENDING (user): `python -m eval.runners.run_redteam --real` once the key is set (about $0.05 on Haiku 5.5, estimate).

## M6 - Voices: BUILT; Kokoro (en/ja) VERIFIED; Parler/OmniVoice PENDING
- Built: voice registry (catalog + bake-off voices + user clips in DB) with engine status, license and demo-only flags;
  persona sets (warm_female, calm_male, energetic_young, formal_senior, one_voice_demo) mapping a voice per language;
  `POST /api/voices/preview` (5-second language-appropriate sample, honest 503 PENDING when an engine is missing);
  adding a persona reference clip requires consent + transcript (OmniVoice clone, always demo-only);
  OmniVoice `ref_from` voices get model-generated reference clips on demand (never a real person);
  voice picker in Settings (preview, set default per agent = new profile version, add/delete clips);
  live switching from the Live Call dock (applies from the next sentence); demo-only badge in transcript and picker.
- Verified: 5 voice tests (real Kokoro preview WAV, pending engine honesty, consent enforcement, live switch);
  UI E2E previews a Kokoro voice and gets the PENDING message for Indic Parler; call E2E switches en voice mid-call
  (greeting kokoro_en_heart -> reply kokoro_en_michael).
- PENDING (user): Indic Parler and OmniVoice voices need the GPU run + native-speaker ratings (M0).
