# Visual references: "Signal Console" direction (2026-11-17)

Source: https://dribbble.com/tags/futuristic-website, opened in headless Chromium on 2026-11-17. I inspected the tag page
and eight shot pages. None of the shots linked to a live product site. Two linked to their studios' own sites
(zajno.com, shakuro.com), which I also opened. No third-party images, code or assets are copied into this repo: only the
principles below, re-implemented from scratch in CSS/SVG/WebGL.

| # | Reference (Dribbble shot) | What I took (principle, not pixels) |
|---|---|---|
| 1 | ANDROAKI "Roughneck" (HUD fashion campaign, tag page card) | Instrument framing: hairline frame with corner ticks, mono micro-labels on the edges (IDs, coordinates, timestamps), boxed terminal-tag buttons |
| 2 | Dmytro Demianenko "Marathon" (tag page card) | Windowed modules: every panel has a title bar ("// LAUNCH STATUS"), an index and a status light; one acid accent on dark |
| 3 | "Audigo - AI Web Design" (dribbble.com/shots/25091151) | The voice is the hero: a live waveform sits inside the headline; small stat call-outs are anchored around the hero object |
| 4 | "Creative Agency Homepage - Dark Futuristic" (/shots/26987452) | Near-black base, a single acid-lime accent, a giant faded wordmark behind content, a vertical side rail with labels |
| 5 | "Futuristic Website Design" robot exhibition (/shots/27253196) | Editorial grid with hairline dividers, numbered sections, generous negative space, registration "+" marks |
| 6 | "AI website design" Koturu (/shots/26247317) | Staggered oversized type, a centred capsule control, warm accent cards for key numbers |
| 7 | Zajno "Retro-Futuristic Cassette Player" (/shots/25961667) + zajno.com | Technical-drawing dimension lines and measurement call-outs used as ornament around a product object |
| 8 | "AI agent website landing page" (/shots/26757421), "Web3 AI Agent Portal" (/shots/26762120) | REJECTED as direction: generic blue gradients, 3D mascots and floating coins read as stock AI |
| - | shakuro.com (live) | Restraint check: large calm type and plenty of space make dense data readable |
| - | "Spektral" (/shots/26505973) | Shot page reached, but its image did not render in headless Chromium: not used |

## Direction: "Signal Console"
ShaOn is an instrument that listens. The orb plus ASCII identity stays; the interface around it becomes a precise,
calm control console:
- **Materials:** graphite near-black, solid panels with hairline borders and corner ticks. No generic frosted glass. One
  acid "signal" accent (phosphor lime) plus cyan for listening; the per-language hues stay.
- **Type:** Unbounded (wide display, Latin only) for page titles and the wordmark; Space Grotesk for UI; JetBrains Mono
  for telemetry and HUD labels; Noto families for all five scripts (DOM text only).
- **Structure:** a left rail on desktop and a bottom dock on phones; numbered modules with title bars; a top status strip
  that always shows mode, model, engine readiness and spend.
- **The orb:** larger, with a measuring reticle, live call-outs (mic RMS, output, state, language) and drag/keyboard
  control. Each state has a distinct reticle behaviour, and the landing demo is labelled "Simulated".
- **Rules:** decoration never sits on top of text or form controls; reduced motion and the Off tier keep every state
  readable without motion.
