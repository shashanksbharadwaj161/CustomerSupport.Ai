# Share ShaOn with a link (free)

Let a client or a friend talk to ShaOn from their own phone or laptop, using a link you send them.
It runs on **your Windows PC**; a free Cloudflare "Quick Tunnel" gives your PC a temporary public https address.
Nothing is paid except the Claude API (only if you added a key in Settings).

## 3 steps

**1. Install cloudflared (once).** Open "Terminal" or "PowerShell" and run:

```powershell
winget install Cloudflare.cloudflared
```

(ShaOn itself must already be set up on this PC - docs/RUNBOOK.md. If cloudflared is missing, the launcher tells you this command.)

**2. Double-click `ShaOn-Share.bat`** in the ShaOn folder. A window opens and:
- checks Python, Node.js and cloudflared,
- starts ShaOn and warms up the speech models (the first time can take several minutes; it shows each language as `loading` / `ready`),
- opens the tunnel and checks the public link really works,
- shows **the link**, **the visitor passcode** and a **QR code**, and saves the link + passcode in `share-link.txt` (and the QR in `share-qr.png`).

**3. Send the link and the visitor passcode** (for example: "Open this on your phone, passcode k7mq-x3fp-9tbw").
Keep the window open. The window also shows an **admin passcode**: keep that one for yourself
(it unlocks Agent Studio, Knowledge, Call Logs and Settings). Visitors can only make calls.

What your visitor sees: a passcode screen, then **Get ready** (test microphone, tap to hear a test sound - needed on
iPhone - connection check, which languages are ready), a banner saying it is a demo on a PC, then **Start call**.

## What the link does NOT give you

- **It dies when your PC sleeps, loses internet, or you close the window.** Set Windows to never sleep while you share
  (Settings > System > Power > Screen and sleep > "Never" while plugged in).
- **The address changes every time** you start sharing (and if the tunnel drops; the window then prints the NEW link
  in green and says the old one is dead). A new visitor passcode is made every launch.
- **Not for the public.** Cloudflare's Quick Tunnels are a free testing service: no uptime guarantee, no SSE, a limit
  of about 200 requests in flight. Fine for a demo, not for a product. Only send the link to people you choose.
- **Not instant.** On a PC without a GPU, expect about 3-6 seconds before each reply (measured on a 4-core CPU).
  The Bengali and Kannada voices are robotic test voices (MMS, non-commercial licence) - say so before the demo.
- **Limits** (change them when starting: `scripts\share.ps1 -MaxCalls 3 -MaxCallSeconds 600`):
  at most 2 calls at the same time (others see "Agent is busy"), each call ends after 5 minutes.

## While sharing

- The window prints a status line every 30 s: tunnel up, which languages are ready, active calls, Claude spend.
- Settings > API key cannot be changed while sharing (protection); spend so far and the cap are shown to the admin.
- Website crawling is admin-only while sharing, with private/internal addresses blocked.
- Stop: press Ctrl+C in the window or close it. The link stops working immediately.

## If something goes wrong

| What you see | What to do |
|---|---|
| "cloudflared ... is not installed" | `winget install Cloudflare.cloudflared`, close the window, double-click again |
| "Python packages missing" | run the command the window prints (inside the ShaOn folder) |
| "Port 8000 is already in use" | ShaOn is already running somewhere: close it, or run `scripts\share.ps1 -Port 8010` |
| Visitor: "Connection lost" | your PC slept or the tunnel restarted: check the window for a NEW link |
| Visitor: "Agent is busy" | two calls are already running; wait, or start with `-MaxCalls 3` |
| Visitor hears nothing on iPhone | ask them to tap "Play test sound" first, and turn off silent mode |
| The window says a language is `unavailable` | that language's engine is not installed on this PC (docs/RUNBOOK.md) |
