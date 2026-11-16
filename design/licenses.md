# Dependency licenses

Every UI dependency is listed here when it is installed (CLAUDE.md). Model and engine licenses are
listed too because they decide demo vs product use.

## UI (web/) - none installed yet (D0/M1)

| Package | Version (pinned) | License | Notes |
|---|---|---|---|
| gsap | to pin at D0 | GSAP Standard License | Free incl. commercial; not for no-code tools competing with Webflow; re-read at release. |

## Python / models

| Component | License | Use |
|---|---|---|
| Pipecat | BSD-2-Clause | M1+ orchestration |
| faster-whisper | MIT | STT ja/en, LID |
| IndicConformer 600M (ai4bharat) | MIT (gated on HF) | STT hi/bn/kn |
| Indic Parler-TTS (ai4bharat) | Apache-2.0 (gated on HF) | TTS product track hi/bn/kn |
| Kokoro-82M | Apache-2.0 | TTS product track en/ja |
| OmniVoice | code Apache-2.0, **weights CC-BY-NC** | **TTS demo only** |
| BGE-M3 | MIT | embeddings |
| anthropic (Python SDK) | MIT | Claude API |
| Eval tool fonts: Noto Sans families (Google Fonts) | SIL OFL 1.1 | recorder/rater pages |
