# ShaOn Voice AI

Configure a voice agent for any business (bank support, tourism, store, clinic, anything), point it at the business's
website, and talk to it live in **Bengali, Hindi, Kannada, Japanese or English**, switching language every turn.
Audio stays on your machine; only text goes to Claude (Haiku 5.5). The only cost is the Anthropic API ($0 plan, DEPLOY.md).

> **DEMO-ONLY WARNING: OmniVoice.** OmniVoice's code is Apache-2.0 but its **model weights are CC-BY-NC
> (non-commercial)**. Any voice produced with it is for private demos only and carries a "demo only" badge in the UI.
> Products must use the Apache-2.0 engines (Indic Parler-TTS, Kokoro). Never clone a real person's voice without consent.

## Start

```bash
scripts/start.sh
```
Open http://127.0.0.1:8000. Missing key or models -> honest demo mode (yellow banner; Settings > Engines).
Full setup from a fresh Windows/WSL2 PC or a Kaggle-only setup: **[docs/RUNBOOK.md](docs/RUNBOOK.md)**.
What works and what is still pending, milestone by milestone: **[STATUS.md](STATUS.md)**.

| Page | What it does |
|---|---|
| Landing | the voice-reactive Signal, how it works, presets |
| Agent Studio | role, persona, style, guardrails, languages, voices, knowledge, tools; every save is a version; rollback |
| Live Call | WebRTC (local) or WebSocket (tunnel) call, transcript with language badges, latency telemetry, voice dock, language override |
| Knowledge | crawl a site you own (robots.txt respected), JS pages rendered, chunks + BGE-M3 in Chroma, site brief, test questions |
| Call Logs | every turn with language, timings, guardrail events; Signal replay |
| Settings | Anthropic key (stored encrypted, never shown again), spend cap, voices with preview, effects tier, engine status |

## How it works
```
Browser (Next.js static UI)  <- WebRTC (SmallWebRTC) or WebSocket ->  FastAPI + Pipecat on your PC
   mic, playback, AnalyserNode -> Signal         Silero VAD -> STT router (language ID, Whisper / IndicConformer)
                                                 -> turn engine: guardrails, retrieval, Claude Haiku 5.5 (stream), tools
                                                 -> TTS router (voice by the reply's script: Kokoro / Indic Parler / OmniVoice)
                                                 SQLite (profiles, versions, calls, spend) + Chroma (knowledge)
```
Repo layout (PLAN.md section 14): `web/` UI, `api/` FastAPI, `agent/` pipeline + routers + prompt + guardrails + knowledge,
`eval/` M0 harness + results, `voices/` catalog, `design/` tokens notes + screenshots + licenses, `deploy/` tunnel,
`docs/` runbook, demo script, eval report, `scripts/` start / doctor / downloads / tests, `tests/` pytest + browser E2E.

## Verify
```bash
scripts/test_all.sh
```
Unit/integration tests (pytest), web build, UI E2E, accessibility scan (axe), and browser calls with a fake microphone over
both transports - all with a scripted LLM, so no API spend.

## Docs
- [PLAN.md](PLAN.md) system plan - [DESIGN.md](DESIGN.md) design - [CLAUDE.md](CLAUDE.md) working rules - [DEPLOY.md](DEPLOY.md) $0 deployment
- [docs/RUNBOOK.md](docs/RUNBOOK.md) setup and operations - [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) client demo
- [eval/results.md](eval/results.md) measurements - [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md) per-language report - [design/perf.md](design/perf.md) visuals vs latency
- [design/licenses.md](design/licenses.md) licenses of every dependency and model

## Rules that matter
- Fake customer data only. Every call starts by saying it is an AI assistant.
- The API key lives encrypted in `data/` (DB value wins over `.env`), never returned to a browser, scrubbed from logs.
- Crawl only sites you own or have permission for. Never commit `.env`, `data/` or model weights.
