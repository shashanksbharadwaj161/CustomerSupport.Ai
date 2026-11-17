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
| Local preview + Settings | `ShaOn-Local.bat`: no passcode, loopback only; API key save/replace/remove/test, model selector (docs catalog + live list on demand), fallback, editable spend cap; all with mocked Anthropic client + a browser E2E with a fake key | your real key + Test key, and the launcher on real Windows - you |
| UI "Signal Console" redesign | console shell, interactive orb stage, all six pages, phone layouts, tiers, reduced motion; axe 0 violations; screenshots in `design/screens/v2/` | native-speaker look at the five scripts; your taste - you |
| Windows installer | `ShaOn-Install.bat` / one-line command: preflight, winget tools, clone/pull, pinned venv, web build, models, self-test, first-run key step, hand-off to the share launcher; 8 stubbed scenarios 44/44 under PowerShell 7; the real pinned install + model download + self-test pass on Linux | **NOT TESTED: real winget, Windows 10/11, Windows PowerShell 5.1, real tunnel, real phone** - you (first run on your laptop) |

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

## One-command Windows installer: BUILT; logic VERIFIED with stubs; real Windows NOT TESTED
How to use: docs/SHARE.md ("Install and share in two steps").
- Built: `ShaOn-Install.bat` -> `scripts/install.ps1` (PS 5.1 + 7, ASCII-only, `-ExecutionPolicy Bypass` for that run only).
  Preflight table (Windows build, free disk: stop under 12 GB / warn under 20 GB, RAM: warn under 8 GB, CPU/GPU, install
  folder, internet) before installing anything. winget installs only what is missing (Git, Python 3.12 - never newer,
  Node LTS 20+, cloudflared, eSpeak NG, FFmpeg, VC++ runtime) with agreements accepted non-interactively; PATH refreshed
  in the same session; winget missing -> exact Store link. Code: clone (bootstrap / one-liner), `git pull --ff-only`
  (checkout) or in-place git connect (ZIP folder); picks `main` only when it exists and contains the installer, says
  which; private-repo failure -> exact Git Credential Manager / `gh auth login` steps. `.venv` (Python 3.12), torch
  from the PyTorch CPU index, pinned constraints `deploy/requirements-cpu.txt`, `npm ci` + production build,
  `scripts/fetch_models.py` (sizes first, progress bars, retries, resume, optional gated IndicConformer with an HF token
  asked once), `scripts/doctor.py`, `scripts/selftest.py` (TTS -> STT per language, offline, no Claude call), then
  `scripts/share.ps1` in the same window. Every step is skipped when already done (hash markers).
- First-run key: `share.ps1` starts the app locally only (key editing allowed, not shared), opens
  http://127.0.0.1:PORT/settings/, the user pastes the key there and presses Enter; key never typed in the terminal,
  logged or sent through the tunnel; spend-limit reminder. Then the shared app starts with key editing locked.
- Verified with stubs (tests/install/run_installer_test.py, `INSTALLER=1 scripts/test_all.sh`, 44/44 PASS under
  PowerShell 7.4): low disk stops first; winget missing; private-repo clone failure; fresh machine (7 tools installed,
  clone, venv, pinned pip, npm, token skipped) with a failed model download -> plain resume message; second run (no
  winget/pip/npm repeat, download resumes, self-test, key step, link + passcode + QR); third run (all skipped, key
  configured, fake key never in output/logs/share-link.txt; 31 s incl. a 25 s share run); partially installed PC +
  ZIP folder + merged main; pip failure -> plain message.
- Verified for real (Linux, Python 3.12): a fresh venv with the installer's exact pip commands (torch CPU index + pinned
  constraints) installs in 132 s, 3.4 GB, `pip check` clean; real model download 7.98 GB; self-test 5/5 languages in
  24 s offline. Interrupted download: finished files kept, the rerun fetched only what was missing (mid-file resume
  relies on huggingface_hub and could not be observed: 300 MB arrived in ~3 s here).
- Found and fixed by the real run: (1) `pyopenjtalk` has no Windows wheel (would need a C++ compiler) -> Japanese G2P
  deps spelled out with `pyopenjtalk-plus` (MIT, Windows wheels, dictionary bundled); (2) eSpeak NG ignores data paths of
  160+ characters (230+ on Windows) and kills the process -> the data folder is copied to a short path when needed;
  (3) `.env` loader let the empty template line shadow a key added below it -> last value wins.
- **NOT TESTED here: real winget, real Windows 10/11, Windows PowerShell 5.1, Windows Defender/SmartScreen behaviour,
  pip wheels on Windows (checked against PyPI only), the real Cloudflare tunnel, a real phone.** Shortest real test: on
  the laptop run the one-line command from docs/SHARE.md, wait for the link, open it on a phone on mobile data.
| Live speech pipeline + website recordings | "TTS context completed with no audio" fixed (regression test); Mithi v2 Flash voices for hi/bn/kn; real two-speaker calls through the website recorded in all 5 languages, 5/5 PASS, first audio 6.4-8.9 s on 4 CPU cores | real Claude conversations (your key) and the same calls on your Windows PC - you |

## Live speech pipeline fix, CPU voices, two-speaker website recordings (2026-11-17): BUILT + VERIFIED here; Claude + Windows PENDING
- **Bug "RouterTTS ... TTS context ... completed with no audio" (the call failure on Windows): FIXED.** Cause: pipecat closes
  an audio context that produces no audio for 3 s (`stop_frame_timeout_s`) and, after 3 such contexts, retires the
  service. ShaOn synthesised a whole sentence in one blocking call; a cold Kokoro sentence took 13-17 s on CPU, so the
  context was closed while it was still being synthesised and the voice died for the rest of the call. Fix
  (agent/pipeline/services.py): synthesis runs in a worker thread and refreshes the audio context every second while it
  works; zero-audio contexts no longer retire the service; long replies are split at clause punctuation and the first
  clause plays while the rest is synthesised; audio goes out in 0.2 s chunks at the engine's own rate (24 kHz Kokoro/Mithi,
  16 kHz MMS) and is resampled by pipecat. Regression test: tests/test_tts_context_regression.py (a 4.5 s fake
  synthesis reproduces the warning without the fix; with it: audio arrives, no warning, a later turn still speaks).
  Server logs of all 5 recordings: 0 "no audio" warnings, 0 error events.
- Other fixes: one Whisper pass for language ID + transcription (no second decode); `SHAON_TORCH_THREADS` caps torch and
  CTranslate2 threads (oversubscription made synthesis 3-5x slower when the browser shares the CPU); Japanese works
  without the 0.5 GB UniDic (falls back to the bundled pyopenjtalk dictionary; test); clear mic errors instead of
  "Connection lost" when no microphone or a busy one; a voice whose engine is not installed falls back to the next CPU voice.
- **Voices evaluated (CPU, eval/results.md "CPU voices compared")**: Kokoro-82M (en/ja, Apache-2.0) kept; **Mithi v2 Flash**
  (Oomni/mithi-v2-flash, Apache-2.0; its self-contained run.py was reviewed: no network/subprocess, safetensors) is the
  new default for hi/bn/kn, MMS-TTS stays as last fallback. Warm RTF Mithi 0.51-0.82, Kokoro 0.24-0.85, MMS 0.15-0.25;
  round-trip recognition CER <= 0.145 for every voice. No MOS / native naturalness rating exists (none invented); the
  Mithi authors say its expression is flatter than larger models. **Indic Parler-TTS: PENDING** (gated on Hugging Face,
  no token here). Indic-Speak: not used (restricted licence). New download: ~0.21 GB (ShaOn-Local.bat fetches it once).
- **Website recordings** (tests/e2e/conversations/: record_conversations.py + web/scripts/conversation_record.mjs +
  report.py). Real /call/ page in headed Chromium; a synthetic CUSTOMER (its own voice) speaks into the browser
  microphone through PulseAudio; the browser's speaker output and the customer are recorded together with the screen by
  ONE ffmpeg process; nothing is edited afterwards. Fake demo bank (Lotus Bay Bank), AI disclosure in the greeting.
  **Agent replies come from the SCRIPTED test provider (`SHAON_LLM_PROVIDER=scripted`), NOT Claude**: there is no Anthropic
  key in this cloud machine and your Windows key was not copied. The UI shows "SCRIPTED REPLIES · NOT CLAUDE" in every
  frame. Everything else (mic capture, VAD, language ID, STT, routing, TTS, playback) is the real pipeline.

  | Language | Result | Agent voice | Customer voice | STT | STT ms (turn 1, 2) | First audio ms (turn 1, 2) | Full | Excerpt |
  |---|---|---|---|---|---|---|---|---|
  | English | PASS | Kokoro af_heart | Kokoro am_michael | Whisper small | 3955, 4356 | 6509, 7074 | 52.8 s | 2.3-32.3 s |
  | Hindi | PASS | Mithi ahana | Kokoro hm_omega | MMS-1B-all | 4278, 4796 | 8290, 8441 | 59.2 s | 2.2-32.2 s |
  | Bengali | PASS | Mithi ahana | Mithi nakul | MMS-1B-all | 4320, 4776 | 8238, 8137 | 57.8 s | 3.1-33.1 s |
  | Kannada | PASS | Mithi ahana | Mithi nakul | MMS-1B-all | 4358, 4700 | 8912, 8739 | 61.8 s | 2.4-34.1 s |
  | Japanese | PASS | Kokoro jf_alpha | Kokoro jm_kumo | Whisper small | 3637, 3298 | 6399, 7963 | 58.9 s | 3.5-33.5 s |

  PASS = 1280x720 H.264 + AAC; both customer lines, the greeting and both answers audible; both customer turns recognised
  in the right language; both answers in native script AND answering the question asked (hours, then lost card); no
  error events. First audio = customer stopped speaking -> first agent audio in the browser (end-of-speech wait + STT +
  reply + first clause of TTS), measured, not trimmed. A full exchange takes 53-62 s, so `shaon-conversation-xx.mp4` is a
  ~30 s EXCERPT (one contiguous cut: greeting, question, the real wait, the answer; labelled EXCERPT on screen) and
  `shaon-conversation-xx-full.mp4` is the whole unedited call. Videos stay out of Git (eval/out/conversations/).
  Earlier failure kept on record: the first Bengali take answered the wrong question (keyword "কার" matched নমস্কার);
  the report was too lenient and called it PASS. Fixed the keywords, added a test, made the report check the answer.
- Where the latency goes on this 4-core machine (browser with software WebGL + recorder on the same cores): STT
  3.3-4.8 s per turn (MMS-1B for hi/bn/kn; Whisper small for en/ja), TTS first clause 2.5-4.7 s. On a PC with an NVIDIA
  GPU both should drop a lot; NOT measured.
- **PENDING**: real Claude replies (put your key in Settings, Test key, one call per language); the same calls on your
  Windows PC (`git pull`, ShaOn-Local.bat); native-speaker ratings of the Mithi voices; Indic Parler-TTS (HF token).

## Local preview, working Settings, Signal Console redesign (2026-11-17): BUILT + VERIFIED here; real Windows NOT TESTED
How to use: double-click `ShaOn-Local.bat` (docs/RUNBOOK.md, "Local preview on Windows").
- **Local preview (no auth)**: `SHAON_LOCAL_PREVIEW=1` (set by `scripts/local.ps1`) disables passcodes and forces key
  editing on, IGNORING stale `ADMIN_PASSWORD` / `VISITOR_PASSCODE` / `ALLOW_KEY_EDIT` from the environment or `.env`;
  refuses to start with `SHAON_EXPOSED`; binds 127.0.0.1 and returns 403 for anything with proxy/tunnel headers or a
  non-loopback peer (no unauthenticated key endpoint can be published). Share mode (`ShaOn-Share.bat`) is unchanged and
  forces local preview off. Verified: pytest (stale passcodes, forwarded requests 403, cannot combine with share mode,
  share mode still gates Settings) + the real launcher under PowerShell 7 with stale env (7/7).
- **Settings**: key save/replace/remove (encrypted at rest, last 4 only, scrubbed), explicit Test key (one tiny call with
  the selected model; friendly 401/404/429 messages). Model selector: catalog cached from Anthropic's model + pricing
  docs (2026-11-03), live list from the Models API (`models.list`, free) only when "Refresh from my account" is pressed;
  explicit IDs only with an opt-in tick, marked unverified. Main + fallback model persisted in the DB, used by call
  replies, guard checks, site briefs and knowledge Q&A; provider cache rebuilt on change; the model the API reports is
  recorded per turn and shown in telemetry/Logs. Per-model request parameters (thinking/effort rules differ per model).
  Unknown model IDs are priced at the highest known rate, so the spend cap can never be bypassed. Spend cap editable;
  a 0 cap the user never set (e.g. from an earlier preview launcher) is reset to 10 USD with a notice; user caps and
  history untouched.
- Verified with mocks only (no Anthropic network call in this session): tests/test_settings_models.py (19 tests: what is
  actually sent per model, persistence across restart, provider invalidation, fallback on 404, refresh, pricing guard,
  cap rules, key never in responses/logs) and tests/e2e/run_settings_e2e.py (18/18: every page opens without login,
  fake key masked, model persists after reload and shows in the status strip, unlisted ID needs the tick, cap edit,
  orb demo states, fake key in no HTTP response and no server log).
- **Redesign "Signal Console"** (design/references.md, DESIGN.md section 1): tokens, console shell (rail / dock / status
  strip), page transitions, SignalStage (reticle, live call-outs, per-state behaviour, drag/keys rotate+zoom, static in
  Off tier and reduced motion), Landing (hero with labelled simulated demo, signal chain, languages, presets, live ready
  check), Live Call (real mic/playback reactivity, transcript, latency telemetry, language/voice controls), Studio,
  Knowledge, Logs, Settings. Checked in Chromium at 1440 px and 390 px (no horizontal overflow on any page), during a
  real fake-mic call (listening / thinking / speaking captured), with reduced motion; axe: 0 violations. Fixed during
  review: orb particles clipped into a square at high levels, CSS layer order, phone ordering, message ordering.
- Windows checkout fix: tracked screenshots named `logs_?id=...png` renamed (`logs_id_...`), screenshot names sanitised,
  and tests/test_repo_hygiene.py fails on any Windows-invalid tracked filename.
- **Pending on your PC**: Hindi/Bengali/Kannada models are not downloaded there (those languages show "not downloaded";
  `ShaOn-Install.bat` fetches them, ~5 GB more); your real key + Test key; one real call. Not tested here: Windows
  PowerShell 5.1 running `local.ps1`, Windows browsers, time-to-first-audio with the new visuals on your PC.
- **Time to first audio, effects on vs off (measured here, n=3 each, English fake-mic call, fake LLM)**: Lite median
  5.08 s (4.02-5.59) vs Off median 4.10 s (3.18-4.20), so the orb still costs about 1 s in THIS sandbox, where the
  browser renders WebGL in software on the same 4 CPU cores as the speech models (before the fix: Lite 5.28-5.33 s vs
  Off 3.70-3.98 s). Mitigation added: on CPU-rendered WebGL, while the models generate, the orb drops to 8 fps and the
  reticle updates about 8 times per second (unless you pick Full). On a PC whose browser uses the GPU for WebGL the cost
  should be smaller; NOT measured. If the delay matters, choose Effects: Off for calls (Settings > Visual effects).

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
