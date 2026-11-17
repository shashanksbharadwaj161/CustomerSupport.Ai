# Dependency licenses

Every UI dependency is listed here when it is installed (CLAUDE.md). Model and engine licenses are
listed too because they decide demo vs product use.

## UI (web/) - pinned in web/package.json

| Package | Version | License | Notes |
|---|---|---|---|
| next | 16.4.6 | MIT | static export served by FastAPI (16.4.4 -> 16.4.6: GHSA-mfr8-8qww-v76h, server-side only, did not apply to the static export) |
| react, react-dom | 19.2.0 | MIT | |
| three | 0.187.0 | MIT | Signal particles, ASCII pass (own shaders, no copied code) |
| @react-three/fiber | 9.8.2 | MIT | |
| gsap | 3.15.0 | GSAP Standard "no charge" License | Free incl. commercial; not for no-code tools competing with Webflow; no reverse engineering; Webflow may change it. Re-read at release. Plugins used: CustomEase, ScrollTrigger. |
| tailwindcss, @tailwindcss/postcss | 4.3.4 | MIT | |
| @fontsource/noto-sans, -bengali, -devanagari, -kannada, -jp | 5.3.x | SIL OFL 1.1 | self-hosted fonts for the 5 scripts |
| @fontsource/space-grotesk | 5.3.0 | SIL OFL 1.1 | UI face (Signal Console direction) |
| @fontsource/unbounded | 5.3.0 | SIL OFL 1.1 | display face: page titles and wordmark, Latin only (Signal Console direction) |
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
| Crawl4AI | Apache-2.0 | JS rendering for the crawler (our own BFS, robots check and limits) |
| chromadb | Apache-2.0 | local vector store (telemetry disabled) |
| Playwright (Python) | Apache-2.0 | crawler JS fallback renderer, E2E |
| Silero VAD (via Pipecat) | MIT | voice activity detection |
| facebook/mms-1b-all (Wav2Vec2 + adapters) | **CC-BY-NC-4.0** | CPU STT candidate for hi/bn/kn: **evaluation / demo only**, never in a product |
| facebook/mms-tts-hin, -ben, -kan (VITS) | **CC-BY-NC-4.0** | CPU voices for hi/bn/kn: **DEMO ONLY, robotic pipeline-testing voices** (badge in UI) |
| transformers | Apache-2.0 | runtime for MMS / IndicConformer / Parler |
| pyopenjtalk-plus | MIT | Japanese G2P for Kokoro (replaces pyopenjtalk: prebuilt Windows wheels, dictionary bundled) |
| SudachiPy / SudachiDict-core | Apache-2.0 | dependencies of pyopenjtalk-plus |
| segno | BSD-3-Clause | QR code for the share link (scripts/share_helper.py) |
| cloudflared (installed by the user, not bundled) | Apache-2.0 | free Quick Tunnel for the share link |

## Evaluation data

| Dataset | License | Use |
|---|---|---|
| google/fleurs (test split; hi_in, bn_in, kn_in, ja_jp, en_us) | **CC-BY-4.0** | Real-audio STT / language-ID evaluation and live-call E2E caller audio. Attribution: Alexis Conneau, Min Ma, Simran Khanuja, Yu Zhang, Vera Axelrod, Siddharth Dalmia, Jason Riesa, Clara Rivera, Ankur Bapna. "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech." IEEE SLT 2022. https://huggingface.co/datasets/google/fleurs. Clips are cached outside the repo (~/.cache/shaon-eval), resampled to 16 kHz; never committed. |
| anthropic (Python SDK) | MIT | Claude API |
| Eval tool fonts: Noto Sans families (Google Fonts) | SIL OFL 1.1 | recorder/rater pages |
