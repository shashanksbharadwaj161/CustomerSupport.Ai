# Remote demo checklist ($0 plan, DEPLOY.md)

Your PC runs everything; a Cloudflare Quick Tunnel gives a temporary public HTTPS URL. Free, but dev/testing grade.

## Before the client call
- [ ] `scripts/doctor.py` shows your demo languages ready; Settings > Test key works locally.
- [ ] `.env`: `ADMIN_PASSWORD` set (12+ chars). The tunnel script refuses to start without it.
- [ ] Anthropic Console: monthly spend limit set. App spend cap set in Settings (default $10).
- [ ] `deploy/tunnel.sh` -> note the `https://<random>.trycloudflare.com` URL it prints.
- [ ] From a PHONE on mobile data (different network): open the URL, sign in, Live Call shows "WebSocket (tunnel)".
- [ ] Make a 2-turn call from the phone. Check: greeting heard, reply heard, transcript shows language badges,
      first-audio in the telemetry strip. If audio stutters, the tunnel is the bottleneck: show the fallback video instead.
- [ ] Automated WebSocket check through the tunnel (from any machine with Node + Playwright):
      `cd web && SHOT=/tmp/tunnel.png node scripts/call_e2e.mjs https://<random>.trycloudflare.com ../tests/e2e/audio/en_question.wav websocket off saturday "."`
      (With auth on: sign in first in that browser profile, or temporarily test without a password on a private network.)
- [ ] Knowledge page through the tunnel shows "progress via polling" (Quick Tunnels do not support SSE).
- [ ] Fallback video recorded (OBS, with audio) and opened in a tab.

## Security that is on automatically through the tunnel
- Password login -> short-lived signed token; every API call and the WebSocket upgrade need it.
- WebSocket Origin checked (CORS does not cover WebSockets); rate limits on login, call start, crawl, previews.
- API key cannot be viewed or changed from the UI (`ALLOW_KEY_EDIT=false`); never returned to any browser.
- Crawler limited to the allowlist (`CRAWL_ALLOWLIST`).
- OmniVoice voices are CC-BY-NC: private demo only. Never share the URL publicly.

## Verified vs pending
- Verified in development: WebSocket transport end to end on localhost (browser E2E), polling fallback, auth, origin check.
- PENDING (you): the actual tunnel run and the phone test - Quick Tunnel WebSocket behaviour is not documented by Cloudflare,
  so test it before relying on it.
