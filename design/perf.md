# Visual effects vs. time-to-first-audio (measured)

Rule (CLAUDE.md / DESIGN.md section 8): test visuals while STT/TTS run; report time-to-first-audio (TTFA) with and without effects.

Setup: Claude Code cloud VM, 4 CPU cores, **no GPU** (Chromium renders WebGL in software via SwiftShader, so the visuals
compete with Whisper/Kokoro for the same CPU). Fake LLM (no network). Whisper small int8 + Kokoro on CPU. Caller audio: Kokoro-generated
"What time does your branch open on Saturday?" played through Chrome's fake microphone. Bank profile with all 5 languages enabled
(language ID runs). One run per row (2026-11-16) - small sample, indicative only.

TTFA = server time from end of caller speech (VAD stop) to the first agent audio frame leaving the server ("first audio" in the Live Call telemetry).
Client column = browser time from the "thinking" state to the "speaking" state.

| transport | effects tier | STT (incl. LID) ms | TTS first sentence ms | TTFA server ms | TTFA client ms |
|---|---|---|---|---|---|
| WebSocket | off | 3061 / 3086 | 854 / 919 | **3924 / 4012** | 3928 / 4016 |
| WebSocket | lite (30 fps cap, DPR 1, 3.5k particles) | 4275 | 938 | **5227** | 5237 |
| WebSocket | auto (drops to lite while generating) | 4357 | 1248 | **5619** | 5693 |
| WebSocket | full (14k particles, DPR 2, uncapped) | 27962 | 1172 | **29156** | 29174 |
| SmallWebRTC | off | 5061 | 1019 | 10495 (first call after start: warm-up) | 4740 |
| SmallWebRTC | lite | 4796 | 1157 | **5969** | 5978 |
| SmallWebRTC | full | 20132 | 1397 | **21543** | 21535 |

Conclusions
- Without a GPU, the Full tier makes the voice pipeline 5-7x slower. Lite costs about 1.2-2 s; Off is fastest.
- Auto already drops Full to Lite during generation. On machines with no GPU the default should be Lite or Off:
  Auto measures frame rate only; it cannot see that rendering is software-based. The Live Call page therefore
  starts in Lite when WebGL reports a software renderer (see `lib/effects.tsx`, `softwareRenderer()`).
- On the demo PC (NVIDIA GPU) the browser renders on the GPU and the models run on CUDA: re-measure there
  (docs/RUNBOOK.md step "Measure visuals vs latency"). PENDING (user).
