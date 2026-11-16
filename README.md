# ShaOn Voice AI

Local web app for configurable voice agents (bank support, tourism, anything) that talk live in
Bengali, Hindi, Kannada, Japanese and English, switching language between turns.

> **DEMO-ONLY WARNING: OmniVoice.** The OmniVoice TTS engine's code is Apache-2.0 but its
> **model weights are CC-BY-NC (non-commercial)**. Any voice produced with it is for private
> demos only and carries a "demo only" badge in the UI. Products must use the Apache-2.0 engines
> (Indic Parler-TTS, Kokoro). Never clone a real person's voice without their consent.

- Plan: [PLAN.md](PLAN.md) - UI: [DESIGN.md](DESIGN.md) - Rules for Claude Code: [CLAUDE.md](CLAUDE.md)
- Deployment ($0: only the Claude API costs money): [DEPLOY.md](DEPLOY.md)

## Status

| Milestone | State |
|---|---|
| Scaffold | done |
| M0 bake-off harness | built; measurements PENDING (needs recordings, native raters, a GPU run) - see [eval/README.md](eval/README.md) |
| D0 design spike | next; final styling blocked on the moodboard (design/README.md) |
| M1-M10 | not started |

## Quick start (M0)

```bash
python scripts/check_hardware.py            # local GPU or free Kaggle notebook?
pip install -e ".[dev]" && pytest           # unit tests, no models needed
```
Then follow [eval/README.md](eval/README.md).

## Rules that matter

- Audio models run locally; only text goes to the Anthropic API. Fake customer data only.
- The API key is entered in the app's Settings page (M1), stored encrypted under `data/`, never sent
  back to the browser. `.env` holds only a fallback. Never commit `.env`, `data/` or model weights.
- Website ingestion only for sites you own or have permission for.
