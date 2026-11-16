# ShaOn Voice AI - hosted demo deployment (milestone M10, after M8)

Local-first stays the rule: M0 to M8 run on your machine. This file is only for putting a working demo online for a client. `deploy/` (Dockerfile, Modal app) is created at M10, not before.

## Decision

| Piece | Host | Why |
|---|---|---|
| Web frontend (Next.js) | Vercel | Fits Vercel well. No GPU or long-lived connections needed. |
| Voice worker: FastAPI + Pipecat + STT/TTS models + Crawl4AI + SQLite/Chroma | A GPU host: Modal first (official Pipecat guide: containerized FastAPI + Pipecat with optional GPU), RunPod as the alternative | Needs a GPU and long-lived audio sessions. |
| Render | Optional, not needed for v1. Only if you later split out a CPU-only control plane (profiles, logs) on Postgres | Render's compute plans list CPU and RAM only, no GPU. Web services are reached over HTTP/HTTPS (80/443) only. |

Do not put the voice worker on Vercel (serverless functions, WebSocket beta with a default 5-minute cap, not built for persistent Python backends) or on Render (no GPU, no UDP).

## Transport

- Chosen by config from M1 (`TRANSPORT=smallwebrtc|websocket`): SmallWebRTC locally, FastAPI WebSocket on the hosted demo. The pipeline is identical either way.
- v1 hosted: Pipecat FastAPI WebSocket transport over HTTPS (TCP/443), protobuf frame serializer on the server, the matching Pipecat JS client transport in the browser. Works through HTTP-only proxies, no TURN needed. Slightly worse under bad networks than WebRTC.
- v2 if latency or jitter hurts: managed WebRTC via Daily transport (supported by Pipecat), or your own signaling server + TURN with SmallWebRTC (the default dev runner is not for production and cannot inject a custom TURN server; WebRTC pages must be served over HTTPS).
- Browser must always be on HTTPS (mic access).

## Steps

1. Dockerfile for `api/` + `agent/` (Python, CUDA base image). Model weights live on a volume, not in the image (download on first start). Crawl4AI needs Chromium in the image, which makes it large: measure image size and cold start.
2. Modal app (or RunPod pod): one GPU container. Keep it warm during the demo window so models stay loaded (`min_containers=1`; older Modal versions called it `keep_warm`; verify the current name in Modal docs at M10). `max_containers=1` (see step 4). Scale to zero outside the demo.
3. Set an explicit function/request timeout above the longest expected call (Modal's default function timeout is 5 minutes and would cut calls). Add a per-call idle timeout in the app so abandoned calls end.
4. Persistent volume for `data/` (SQLite, Chroma, voices, encrypted key secret file). SQLite on a Modal Volume: changes persist only after a commit and concurrent writers from several containers are unsafe. So: exactly one container, `volume.commit()` after every call, crawl and settings change. If the demo ever needs more than one container, move the control plane (profiles, logs, settings, spend) to Postgres (that is when the optional Render split makes sense).
5. Secrets as platform secrets, never in the repo: `ADMIN_PASSWORD`, `SPEND_CAP_USD` (default cap), optionally `ANTHROPIC_API_KEY` as a fallback. Primary key path: entered once in the Settings page, stored encrypted in the DB (CLAUDE.md). On hosted, set `ALLOW_KEY_EDIT=false` after the key is in place.
6. Spend cap and spend-so-far are stored in the DB, not in memory, so restarts do not reset them. Also set a spend limit in the Anthropic Console.
7. Vercel project for `web/`, env var `NEXT_PUBLIC_API_URL` = worker URL. CORS locked to the Vercel domain.
8. Auth on the worker, not only on the web app. The worker URL is public, so a Vercel-only password is bypassable. Shared password login issues a short-lived signed token; the worker requires it on every REST call and on the WebSocket upgrade. Use an app-level password, not Vercel's built-in password protection (a paid feature).
9. WebSockets are not covered by CORS (browsers do not apply CORS to the WebSocket handshake). The worker checks the `Origin` header against the allowlist itself, in addition to the token.
10. Rate limiting on login, call start and crawl endpoints (the M2 auth + rate-limit layer, configured here).
11. Health page (`/api/health`): models loaded, GPU memory, key present (never the key), spend so far.
12. Smoke test from a different network and a phone before the client call. Record a fallback video.

## Licensing and safety for a hosted demo

- OmniVoice weights are CC-BY-NC. A private, password-protected client demo is the limit; do not make it public. Switch to the Apache-2.0 engines (Indic Parler, Kokoro/Qwen3-TTS) for anything beyond a demo.
- Crawl endpoint: only sites you own or have permission for. Add an allowlist of domains on the hosted demo.
- Fake data only on the bank demo.
- Set a spend limit in the Anthropic Console in addition to the app cap, and a budget alert on the GPU host.

## Open checks before M10 (verify against Modal docs at M10, do not trust memory or list prices)

- GPU availability per region, and whether region selection is available on our plan (drives India/Japan latency).
- Whether `min_containers` or `keep_warm` is the current setting name.
- Cold-start time with weights on a volume (measure), plus image size with Chromium.
- Real GPU price on Modal vs RunPod for our model set (measure).
- Whether Bengali/Kannada/Hindi voices pass M0. If not, hosting does not fix it.
- Whether WebSocket transport latency is acceptable from India and Japan to the GPU region.
