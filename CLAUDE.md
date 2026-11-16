# CLAUDE.md - ShaOn Voice AI

Read PLAN.md (system) and DESIGN.md (UI) first; DEPLOY.md only for M10 (hosted demo). Build one milestone per session. M0 (bake-off) comes first, D0 (design spike) runs alongside M0/M1.

## Stack rules
- Frontend: Next.js (React) + Tailwind. Backend: Python, FastAPI + Pipecat (SmallWebRTC). SQLite + Chroma.
- LLM: Anthropic API, model `claude-haiku-5-5`, streaming on, prompt caching for system prompt + site brief. Sonnet (`claude-sonnet-5-5`) as per-language fallback. Never commit keys.
- API key handling (decision 2026-11-16): the key is entered in the app's Settings page and stored server-side only, encrypted at rest with a secret generated on first run into a 0600 file under `data/`. Never returned to the browser (show last 4 only). "Test key" button makes one tiny call. DB value wins over `ANTHROPIC_API_KEY` in `.env` (the `.env` value is the fallback; `.env.example` documents it). `ALLOW_KEY_EDIT=false` disables editing (hosted); otherwise editing needs `ADMIN_PASSWORD`. Scrub the key from logs, tracebacks and transcripts.
- Spend cap and spend-so-far live in the DB (survive restarts). Claude calls stop when the cap is reached.
- Audio models run locally. Only text goes to the Anthropic API. Fake customer data only.
- STT and TTS sit behind small interfaces (`STT`, `TTS`), selected per language by config. Load models on demand.
- Layout as in PLAN.md section 14. Do not create files outside it without saying why.
- Agent profile = one JSON document, versioned on every save.
- OmniVoice weights are CC-BY-NC: mark every use as demo-only in code comments, README and the UI badge. Do not remove the warning.
- Voice reference clips: only consenting speakers or model-generated clips. Never clone a real person without consent.
- Website ingestion: same-domain only, page/depth limits, our own robots.txt check, clear user agent, only sites the user owns or has permission for.
- Reference repos in PLAN.md section 2: do not copy code from AGPL (VoiceStudio) or non-commercial-weights projects into the product. Do not copy third-party design components without checking their license.

## System prompt builder (per profile)
- Role from agent type, then persona, tone, per-language politeness.
- Reply in the language of the caller's last turn (Bengali, Hindi, Kannada, Japanese or English), in NATIVE SCRIPT, never romanized. If the caller mixes languages, use the dominant one.
- Write numbers, currencies and dates as words in the reply language (TTS mispronounces digits).
- Default 1-2 short sentences per turn. No markdown, lists, emojis or URLs read aloud.
- Answer only from the site brief, retrieved chunks or tool results. If unsure, say you will connect a human.
- Read back IDs, phone numbers and amounts to confirm.
- Guardrails section from the profile.
- First line of every call says it is an AI assistant.

## Language routing rules
- Reply language is detected from the reply's script (Unicode ranges), not trusted from the model.
- Low LID confidence keeps the previous language. Manual override in the UI always wins.
- Thresholds come from `eval/results.md`, not guesses.

## Guardrails
- Layer 1 prompt rules, layer 2 checker (input and reply, strict JSON verdict, fail closed to handoff), layer 3 tool allowlist.
- Log every trigger. Maintain the red-team set (10 attacks per preset, include jailbreaks in each language). Report pass rate honestly.

## UI rules (see DESIGN.md)
- Tokens live in one file; no hard-coded colors or durations in components.
- ASCII art is Latin/symbols only. Language content always renders as DOM text with Noto fonts.
- Effects tiers (Auto/Full/Lite/Off) and `prefers-reduced-motion` are required for every animated component.
- Test visuals while STT/TTS models are running. Report time-to-first-audio with and without the effects.
- Pin the GSAP version. Check licenses of every UI dependency and note them in `design/licenses.md`.
- Moodboard and the reference inventory live in `design/`. If they are missing, stop and ask for them before final styling.

## Working style
- Before coding a milestone, state the plan in 5 lines, implement, then run the evals/tests and report numbers.
- Report measured latency, error rates and native-speaker ratings, not guesses. Put results in `eval/results.md`.
- If an engine fails a check, say so and propose the fallback in PLAN.md section 16.
- Ask before adding paid services or hosted audio APIs.
- Transport is chosen by config from M1: SmallWebRTC locally, FastAPI WebSocket on the hosted demo (DEPLOY.md).
- Auth + rate-limit layer lives in `api/` from M2 (no-op locally unless `ADMIN_PASSWORD` is set).
- GPU for M0: run `scripts/check_hardware.py`. Modal only if no NVIDIA GPU or under ~12 GB VRAM, budget $15 with an alert, and ask before starting anything paid (the user creates the Modal account/token).
- Commit small and often; never commit models, `.env`, `data/`.
