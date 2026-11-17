# ShaOn Voice AI - $0 deployment plan (replaces the Modal/RunPod version)

Budget rule: the only money spent is the Claude API. Everything else must be free. Nothing in this repo may require a paid host, a paid GPU or a paid add-on.

## Decision

| Need | $0 answer | Notes |
|---|---|---|
| Run the voice worker (STT/TTS models, Pipecat, FastAPI, crawler, SQLite, Chroma) | YOUR OWN PC. Local-first stays the rule. | No free host offers a GPU for a live always-on service. |
| Show the client | Screen-share or in-person live demo from your PC; plus a recorded fallback video | Free, no uptime risk from third parties. |
| Remote access for the client (optional) | Cloudflare Quick Tunnel from your PC (`cloudflared tunnel --url http://localhost:PORT`) | Free, but dev/testing only: random URL, no uptime guarantee, 200 in-flight request cap, SSE not supported. WebSockets are not mentioned in its docs: test the WebSocket transport through it before relying on it. Your PC must stay on. |
| Frontend hosting (only if you use a tunnel) | Vercel Hobby (free) | Password Protection is a paid Pro add-on: use the app-level password. Check Vercel's fair-use terms for showing a paying client; the Hobby page does not state the commercial-use rule. If in doubt, serve the frontend from your PC too. |
| M0 bake-off if your PC has no usable GPU | Kaggle free GPU notebooks (T4/P100 class, about 30 GPU-hours a week, sessions of 9-12 hours; check your account page for the real weekly number), Colab free as backup | Batch scripts only: generate TTS audio, run STT on recorded files, write eval/results.md. Not for live calls (Colab free does not allow SSH or web UIs without a paid balance). |
| Render | NOT USED | No GPU, free web services spin down after 15 minutes of no traffic (WebSocket messages count), no persistent disk, free Postgres expires after 30 days. |
| Modal / RunPod | NOT USED by default | Paid. Only revisit if you decide to spend later. |

## Transport

- Chosen by config (`TRANSPORT`) from M1; the pipeline is identical either way.
- Local: SmallWebRTC (UDP on localhost, no TURN needed).
- Through a tunnel: Pipecat FastAPI WebSocket transport (TCP over HTTPS). Test it first.
- Browser must be on HTTPS when not on localhost (mic access).
- Because Quick Tunnels do not support SSE, every SSE stream in the app (crawl progress, M4) also gets a polling fallback endpoint the UI switches to when tunneled.

## Security rules (apply even locally; they cost nothing)

- Server-side auth: the worker checks the admin password or a short-lived token on every REST call and on the WebSocket upgrade. The tunnel URL is public to anyone who has it.
- Check the `Origin` header on the WebSocket handshake (CORS does not cover WebSockets).
- Anthropic API key entered in Settings: stored server-side, encrypted, never returned to the browser (last 4 shown), "Test key" button, scrubbed from logs. `ALLOW_KEY_EDIT=false` when exposed through a tunnel.
- Spend cap and spend-so-far stored in the database, so a restart does not reset them. Also set a limit in the Anthropic Console.
- Crawler: only domains on an allowlist when exposed.
- Fake data only for the bank demo.

## Keeping the Claude API bill small (the only cost)

- Model: Claude Haiku 5.5. Prompt caching for the system prompt and site brief.
- Replies capped at 1-2 short sentences (also better for voice).
- Guardrail checker default: cheap local rules on input (keywords, patterns) plus ONE combined Claude check on the reply. Full two-call checking is a settings toggle.
- Site brief: generated once per crawl, cached, regenerated only on re-crawl.
- Evaluation runs (M0) use the shortest test set first.
- Default `SPEND_CAP_USD=10`, adjustable in Settings.

## What $0 cannot give you

- A public, always-on URL for the client to call any time. That needs a GPU host (paid) or a client-side install.
- Guaranteed speed: if your PC has no NVIDIA GPU, M0 decides which smaller models the live demo uses, and Kannada/Bengali replies may be slow. Say so to the client up front, or show the recorded video for those languages.
- OmniVoice is non-commercial (CC-BY-NC): demo only.

## If you ever decide to spend (not the plan)

Modal or RunPod GPU container with volume storage (one container, commit after each call, SQLite risky with several writers), explicit function timeout above the longest call, `region=` pinning (check GPU availability), WebSocket origin and token checks, Postgres if you scale past one container. Verify Modal's current settings (`min_containers` vs `keep_warm`) at that time.

## Public link at $0: PC + Quick Tunnel (decision 2026-11-17)

How to use it: docs/SHARE.md (double-click `ShaOn-Share.bat`). How it works:
- `scripts/share.ps1` runs on the user's PC (Windows PowerShell 5.1 / PowerShell 7; `scripts/share.sh` wraps it on macOS/Linux):
  production build, the app in exposed mode, real per-language model warm-up, `cloudflared tunnel --url`, public `/health`
  check, link + visitor passcode + QR, watchdog that restarts the tunnel and prints the NEW link when the old one dies.
- One origin: the FastAPI process serves the static web build, `/api` and the call WebSocket on one local port, so one tunnel
  URL is enough and the browser sees a single https origin. A separate reverse-proxy process would only add a hop for the
  audio stream, so the app process itself plays that role.
- Security while shared: per-launch visitor passcode (calls only) and admin passcode (Studio, Settings, key, knowledge,
  logs), checked server-side for REST and the WebSocket upgrade; Host and Origin must be localhost or the tunnel host learned
  at launch; per-IP rate limits using the client IP Cloudflare forwards; max concurrent calls (default 2) and max call length
  (default 5 min); key editing off; ingestion admin-only with an SSRF guard (resolved addresses, every redirect hop, JS
  rendering off). Tested in tests/test_share_security.py and the share E2E scripts.

### Hosting options rejected for $0
These reasons come from the project owner's research (November 2026); re-check them before revisiting the decision.

| Option | Why not |
|---|---|
| Hugging Face Docker Spaces | Docker Spaces need a paid plan now; free CPU Spaces would also be too slow for live speech models. |
| Render, Vercel | No GPU, and not built to host CPU speech models for live calls (Render free sleeps and has no persistent disk; Vercel functions are short-lived). |
| Oracle Cloud Always Free (Ampere) | Allowance halved to 2 OCPU / 12 GB, and "out of capacity" errors when creating instances: not reliable enough for a client demo. |
| Modal / RunPod / other GPU clouds | Paid. |

Decision: the user's own PC runs everything; a Cloudflare Quick Tunnel gives a temporary public https link. Trade-offs
(written into docs/SHARE.md): the link dies when the PC sleeps or the window closes, the URL changes every run, no uptime
guarantee, not for public traffic.
