# STATUS

Honest state of every milestone. VERIFIED = run and checked in this repo's tests or by a measured run.
PENDING = cannot be done here; says who must do it.

## At a glance (2026-11-17)

| Area | Works now (verified in this VM: 4 CPU, no GPU, no API key) | PENDING - who |
|---|---|---|
| Voice calls | en + ja end to end on CPU, both transports, language switch mid-call, live voice switch (barge-in is implemented but not yet tested) | GPU latency on your PC - you; barge-in test - next session |
| Languages hi / bn / kn | REAL speech (FLEURS) end to end on CPU: LID 100% (n=50 each), MMS STT WER hi 19.6% / bn 30.9% / kn 26.1% (n=20), live calls + switches 6/6 pass, first audio 5.2-7.1 s; MMS voices are robotic demo-only | IndicConformer (HF token), Indic Parler / OmniVoice (GPU), native ratings - you / native speakers |
| Claude replies | provider, caching, spend cap, prompt builder (tested with a fake LLM) | real key in Settings + Test key - you |
| Knowledge | crawl (robots, limits, JS), BGE-M3 retrieval hit@3 100% in 5 languages | site brief needs the key - you |
| Guardrails | local layers 100% of local-layer attacks, 0 false positives | Claude red-team run - you (needs key) |
| UI | all pages, tiers, reduced motion, axe 0 violations, 64 screenshots | Folded Signal moodboard + assets for final styling - you |
| M0 numbers | harness, Kaggle runbook, recorder, rater | native recordings + ratings - native speakers; GPU run - you / Kaggle |
| Share link (PC + Quick Tunnel) | `ShaOn-Share.bat` launcher (run under PowerShell 7 with a stub tunnel), visitor/admin passcodes, Host/Origin checks, busy + max length, SSRF guard, Get-ready screen; 5 languages + 3 switches through the share-mode server | **public tunnel path: NOT TESTED** (sandbox cannot reach the Cloudflare edge); Windows PowerShell 5.1 + real phone - you |

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

## M7 - UI build-out: BUILT + VERIFIED (provisional tokens)
- Built: all DESIGN.md pages - Landing (ASCII wordmark hero, pinned scroll story "How ShaOn works" with cross-fades,
  5-language section in native scripts, spatial 3D preset gallery with keys/drag, liquid-metal CTA, footer with the
  OmniVoice demo-only notice), Agent Studio, Live Call (Signal, floating transcript, telemetry strip, voice dock),
  Knowledge (drop zone, crawl graph collapsing into the brief), Call Logs (dense list, detail, per-turn timings,
  guardrail events, Signal replay from stored timings), Settings (API key, spend, voices, effects, engines).
  Effects tiers + reduced motion apply to every animated component (Signal, ASCII, GSAP timelines jump to end states in Off).
- Verified: axe-core WCAG 2.1 A/AA scan: 0 violations on all 7 pages (after fixing contrast of dimmed badges and faint text);
  64 Playwright screenshots in design/screens/ (7 pages + call detail x full/lite/off/reduced x desktop/phone, plus scroll states);
  no page errors; time-to-first-audio with/without effects in design/perf.md.
- PENDING (user): "Folded Signal" moodboard, reference inventory and assets -> final styling pass (tokens are provisional).

## M8 - Demo hardening: BUILT + VERIFIED
- Built: one-command start (`scripts/start.sh`: venv detection, dependency check, refuses non-local listening without a password,
  port check, builds the UI when stale); first start seeds the two demo agents with their FAKE sites (bank + travel, crawled
  from `/demo-sites/`); `scripts/doctor.py` checklist with exact fix commands; `scripts/test_all.sh` (everything, $0);
  STT falls back to Whisper inside the same turn if a GPU engine fails to load (and says so); login gate moved to the root
  layout (found by the exposed-mode E2E: pages fetched data before login); `docs/DEMO_SCRIPT.md` talk track + failure plays;
  silent walkthrough video `docs/demo/walkthrough-silent.webm` (`web/scripts/record_demo.mjs`); README rewritten.
- Verified: `scripts/test_all.sh` stages all green: 125 tests, typecheck, build, demo seeding (2 sources ready), 5 UI suites,
  axe 0 violations, call E2E en WebRTC / en WebSocket / ja WebSocket (first audio 4.1-4.5 s on CPU, effects off).
  Found + fixed: Chrome ignores fake-mic paths containing "..".
- PENDING (user): a real fallback video WITH audio, recorded on the demo machine with the key and GPU engines (OBS).

## M10 - $0 remote demo (tunnel) + runbook: BUILT; tunnel itself PENDING (user)
- Built: `deploy/tunnel.sh` (refuses to start without a 12+ character ADMIN_PASSWORD; sets SHAON_EXPOSED=1,
  ALLOW_KEY_EDIT=false, crawl allowlist; starts the app and a Cloudflare Quick Tunnel), `deploy/CHECKLIST.md`
  (phone test on mobile data, WebSocket test, polling check, fallback video), Knowledge progress defaults to polling
  off-localhost (Quick Tunnels do not support SSE), `docs/RUNBOOK.md` (Windows + WSL2 + NVIDIA path, Kaggle-only path,
  HF token, downloads, recording + rating, engine switching per language, troubleshooting).
- Verified: exposed mode locally: API without token -> 401, WebSocket without token -> refused, password login -> token ->
  full WebSocket call (in `scripts/test_all.sh`). WebSocket transport E2E on localhost.
- PENDING (user): running the real Quick Tunnel and the phone test (no public tunnel was opened from this sandbox).

## Share by public link ($0, PC + Quick Tunnel): BUILT + VERIFIED locally; public tunnel path: NOT TESTED
How to use: docs/SHARE.md. Design + rejected hosts: DEPLOY.md "Public link at $0".
- Built: `ShaOn-Share.bat` -> `scripts/share.ps1` (prerequisites, production build, exposed mode, per-language warm-up,
  Quick Tunnel, public /health check, link + visitor passcode + QR, `share-link.txt` (gitignored), watchdog that restarts
  the tunnel and prints the NEW link, status line every 30 s). One origin: FastAPI serves web + /api + call WebSocket.
- Security (tests/test_share_security.py, 21 tests, mutation-checked): per-launch visitor passcode (calls only) and admin
  passcode, REST + WebSocket upgrade; Host/Origin limited to localhost + the learned tunnel host; per-IP rate limits from
  CF-Connecting-IP (only trusted from loopback); max calls (2) -> "busy"; max call length (5 min); key edit off;
  ingestion admin-only, SSRF guard on every redirect hop (10 SSRF URLs refused); passcodes/tokens scrubbed from logs.
- Visitor UI (web/scripts/share_ui_e2e.mjs, 5/5 PASS): wrong passcode rejected, Get ready (mic, speaker tap, WebSocket
  check, per-language badges), second caller sees "busy", 20 s max length ends the call, offline mid-call -> friendly
  "connection lost" screen. Phone layout 390 px (design/screens/share-*-phone.png), effects Auto = Lite on phones.
- Launcher (tests/share/run_launcher_test.py, 7/7 PASS under PowerShell 7.4 on Linux with a stub cloudflared): link
  printed, share-link.txt has link + visitor passcode only, no admin passcode / key in logs, tunnel drop -> NEW link,
  clean stop.
- Live calls through the share-mode server (Host = tunnel host, visitor passcode, real CPU engines, fake LLM):
  8/8 PASS (one run each, 4-core CPU, 2026-11-17). First audio (ms): en 3246, ja 2937, hi 4110, bn 3517,
  kn 5054; switches hi->en 4314/3156, bn->ja 3579/2820, kn->hi 5026/4369. Raw: eval/out/share_e2e.json.
- Fixed during this pass: first Hindi call took 108 s (MMS adapter not really warmed) -> warm-up now transcribes 1 s per
  language and readiness waits for it; the Get-ready WebSocket check used the call-start rate limit, so a 5th quick
  call was silently refused -> own bucket, and a rate-limited start now shows "wait a minute".
- **public tunnel path: NOT TESTED.** cloudflared got a trycloudflare URL from this sandbox but could not connect to the
  Cloudflare edge (no direct egress). Shortest manual test (5 min): `winget install Cloudflare.cloudflared`, double-click
  `ShaOn-Share.bat`, wait for the green link, open it on a phone using mobile data (Wi-Fi off), enter the visitor
  passcode, Get ready all green, one call in English and one in Hindi; then close the window and check the link is dead.
- Also not tested here: Windows PowerShell 5.1 itself, winget paths, Windows Defender prompts, a real iPhone/Android.

## M9 - Eval report skeleton: BUILT
- `python -m eval.make_eval_report` -> `docs/EVAL_REPORT.md`: per-language table (STT, LID, Claude, retrieval, TTS rating,
  verdict), switching, guardrails, honest weak spots, product-track notes; built only from measured files, PENDING otherwise.
- Currently measured in it: cross-lingual retrieval (all 5 languages), guardrails local layers, Kokoro en/ja speed.


## Indic real-audio pass (hi / bn / kn): MEASURED on CPU with FLEURS read speech; product engines PENDING
Data: google/fleurs test split (CC-BY-4.0, Conneau et al. 2022), seed 20261116, clips cached outside the repo (~100 MB).
**Caveat:** clean read Wikipedia-style speech, not phone calls - optimistic. Whisper small/base are CPU stand-ins. MMS = CC-BY-NC.

| lang | STT engine (CPU, routed) | WER / CER (n) | LID app decision (n=50) | TTS voice (CPU) | RTF | round-trip CER (proxy) | live-call E2E | license status |
|---|---|---|---|---|---|---|---|---|
| hi | mms-1b-all adapter hin | 19.6% / 7.1% (20) | 100% | Kokoro hf_alpha (MMS hin as 2nd) | 0.33 (MMS 0.22) | 6.0% (MMS 9.7%) | pass (3/3 turns) | MMS CC-BY-NC demo; Kokoro Apache-2.0 |
| bn | mms-1b-all adapter ben | 30.9% / 9.1% (20) | 100% | MMS ben (robotic) | 0.18 | 8.0% | pass (2/2) | CC-BY-NC demo only |
| kn | mms-1b-all adapter kan | 26.1% / 3.9% (20) | 100% | MMS kan (robotic) | 0.18 | 8.4% | pass (2/2) | CC-BY-NC demo only |
| en | Whisper small (greedy) | 5.3% / 2.4% (50) | 100% | Kokoro af_heart | 0.28 | - | pass (1/1) | MIT / Apache-2.0 |
| ja | Whisper small (greedy) | CER 12.7% (50) | 100% | Kokoro jf_alpha | 0.33 | - | pass (1/1) | MIT / Apache-2.0 |

- Whisper small on CPU is unusable for Indic: WER hi 78%, bn 103%, kn 100% (repetition loops, wrong-script output); base worse.
- Found + fixed: CPU Whisper now greedy without temperature-fallback retries (retries took ~1.6 min per Kannada clip);
  script flip may no longer override a confident LID (it mislabelled 2/50 Bengali clips); LID probabilities renormalized over
  enabled languages (Whisper puts Hindi mass on Urdu); language ID is detection-only, so a Hindi/Bengali/Kannada turn is
  transcribed once: first audio hi 8.7 -> 5.8 s, bn 8.6 -> 5.3 s, kn 12.1 -> 6.7 s (median, same calls).
- LID thresholds proposed from the sweep (threshold 0.3, prev_bias 0, script flip below 0.6): CPU / read-speech ESTIMATES.
- Per-language STT order is configurable (`agent/engines.json`), derived from measurements by `python -m eval.routing_from_results --write`;
  every skip / fallback is logged per turn.
- PENDING (user): IndicConformer (gated: HF token), Indic Parler + OmniVoice + Whisper large-v3 on the GPU, real call audio,
  native-speaker review of the machine-written reply lines and ratings of every voice.
