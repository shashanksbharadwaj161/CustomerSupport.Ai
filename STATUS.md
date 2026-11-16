# STATUS

Honest state of every milestone. VERIFIED = run and checked in this repo's tests or by a measured run.
PENDING = cannot be done here; says who must do it.

## D0 - Design spike: BUILT
- Built: Next.js 16 static export in `web/`, single tokens file `web/src/styles/tokens.css` (JS reads it back via `lib/tokens.ts`), self-hosted Noto fonts for all 5 scripts, effects tiers Auto/Full/Lite/Off + `prefers-reduced-motion` + pause when hidden (`lib/effects.tsx`), the Signal (R3F particles, 7 states, 5 language motifs, AnalyserNode-driven) with a static fallback, GPU ASCII post-process (Latin glyphs only), landing hero with the wordmark assembling from particles, Signal lab page.
- Verified: build + typecheck; screenshots in `design/screens/` for full/lite/off on desktop and phone; lab page frame rate in this VM (software WebGL, no GPU): full 48 fps, lite/off 60 fps (lite is capped to 30 fps rendering by design; page rAF stays 60).
- PENDING (user): moodboard, reference inventory and assets in `design/` for the final styling pass. Tokens are provisional.
