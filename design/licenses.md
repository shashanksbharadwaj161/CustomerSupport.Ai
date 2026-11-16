# Dependency licenses

Every UI dependency is listed here when it is installed (CLAUDE.md). Model and engine licenses are
listed too because they decide demo vs product use.

## UI (web/) - pinned in web/package.json

| Package | Version | License | Notes |
|---|---|---|---|
| next | 16.4.4 | MIT | static export served by FastAPI |
| react, react-dom | 19.2.0 | MIT | |
| three | 0.187.0 | MIT | Signal particles, ASCII pass (own shaders, no copied code) |
| @react-three/fiber | 9.8.2 | MIT | |
| gsap | 3.15.0 | GSAP Standard "no charge" License | Free incl. commercial; not for no-code tools competing with Webflow; no reverse engineering; Webflow may change it. Re-read at release. Plugins used: CustomEase, ScrollTrigger. |
| tailwindcss, @tailwindcss/postcss | 4.3.4 | MIT | |
| @fontsource/noto-sans, -bengali, -devanagari, -kannada, -jp | 5.3.x | SIL OFL 1.1 | self-hosted fonts for the 5 scripts |
| @fontsource/space-grotesk | 5.3.0 | SIL OFL 1.1 | display face (provisional until moodboard) |
| @fontsource/jetbrains-mono | 5.3.0 | SIL OFL 1.1 | mono / telemetry / ASCII glyph atlas |
| playwright (dev) | 1.63.0 | Apache-2.0 | screenshots and E2E tests |
| typescript (dev) | 5.9.3 | Apache-2.0 | |

No third-party design components were copied. Reference ideas (liquid-metal button, capsule nav, dock,
particle hero, ASCII) are re-implemented from scratch.

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
