# ShaOn Voice AI - design system and art direction

Goal: a spectacular, futuristic, award-level interface: shaders, particles, ASCII art, scroll and motion choreography, a voice-reactive hero. The interface must still be fast, readable in five scripts, and usable.

## 1. Art direction

- Primary direction: your APPROVED "Folded Signal" moodboard (from your handoff notes). I have not seen it. Copy its files into `design/moodboard/` and extract palette, type and shape language into the tokens below before building. The tokens in section 3 are provisional until then.
- Rejected direction: NOVARA (research history). Do not use it as a reference.
- Concept hook: a "signal" that listens, thinks, speaks and morphs between languages. The voice is the hero graphic.
- Reuse your existing assets from the shaon-tech project: two generated image masters, their 12 deployed AVIF/WebP variants, original website graphics, and the Flow video experiment (all from your notes). Copy into `design/assets/`. Do not reuse assets you do not own.

## 2. Reference register (20 main references from your inventory)

The full inventory (20 main references, all 83 recorded HorizonX entries, directories, tools, generated assets) is a file on your PC: `C:/Users/SHASH/Documents/Codex/2026-10-03/https-github-com-shashanksbharadwaj161-shaon-tech/outputs/Design-reference-and-asset-inventory.md`. I could not read it. Copy it into `design/reference-inventory.md` so Claude Code can use all 83 entries. Exact links for the Jitter, Cove Light, Optikka and MotionArray examples were not preserved.

Use references for inspiration and technique. Do not clone layouts, copy code or assets. Check the license of any component-marketplace item (threeui, 21st.dev, HorizonX, Framer marketplace) before copying code; default is to re-implement the idea.

| Reference | Link | Idea | Used for in ShaOn |
|---|---|---|---|
| Unicorn Studio | https://www.unicorn.studio/ | Interactive shaders, atmospheric motion | Landing hero backdrop (optional, see 5) |
| Zajno Motion | https://motion.zajno.com/ | Morphing, masking, depth, animated menus. It is a motion teaching guide (easing, stagger, morph, masking, parallax, zoom) built in Webflow with pre-rendered media, not a code source | Motion principles and Studio tab transitions |
| basement | https://basement.studio/showcase#list | Portfolio presentation, immersive navigation | Agent preset gallery |
| KILN | https://horizonx.so/explore/kiln-studio-landing | Spatial imagery, oversized type | Hero and section typography |
| sublevel.studio | https://threeui.com/landing-pages/sublevel-studio-landing-page | Experimental studio presentation | Landing storytelling blocks |
| Glass Portfolio | https://21st.dev/@larsen66/templates/glass-portfolio | Reflective hero, expandable dock | App dock navigation |
| Supaste | https://www.supaste.com/ | Capsule navigation | Top capsule nav |
| Sable dock | https://threeui.com/css/animated-top-dock | Animated nav, active states | Dock active states |
| DNA Carousel | https://www.framer.com/marketplace/components/dna-carousel/ | Spatial project browsing | Browsing crawled pages and agent presets |
| Scroll Zoom Reveal | https://scrollzoomreveal.framer.website/ | Scroll-driven expansion | Landing scroll reveal |
| Liquid Metal Button | https://threeui.com/buttons/liquid-metal-button | Chrome shader buttons | Primary "Start call" button |
| AURA | https://21st.dev/@larsen66/templates/aura-svelte-gsap | Text illumination, section pacing | Text reveal and pacing |
| Orvane | https://horizonx.so/explore/orvane-particle-hero | Particle hero | Voice orb particles |
| Digital Wave Field | https://horizonx.so/explore/digital-wave-field-hero | Responsive wave/grid effects | Audio-reactive wave field |
| ARQ-01 | https://horizonx.so/explore/arq-01-carry-the-horizon | Scroll transformations | Ingest-progress storytelling |
| Immersive Robotics | https://horizonx.so/explore/immersive-robotics-landing | Technical storytelling | "How ShaOn works" section |
| Halovane | https://horizonx.so/explore/halovane | Particle morphing | Language-switch morph |
| Kreivo | https://horizonx.so/explore/kreivo | Visitor-controlled effects | Pointer/voice-controlled effects |
| GSAP Motion Lab | https://horizonx.so/explore/gsap-scroll-motion-lab | Motion experiments | Timeline and scroll patterns |
| NOVARA | https://horizonx.so/explore/novara-creative-studio | REJECTED direction | Do not use |

## 3. Design tokens (provisional until Folded Signal is extracted)

- Color roles: `bg`, `surface`, `surface-raised`, `ink`, `ink-muted`, `signal` (primary glow), `signal-alt`, `warn`, `danger`, plus one hue per language (en, ja, hi, bn, kn) used for badges, orb tint and ASCII tint. Dark theme first; build a light theme only if time allows.
- Type: oversized display face (KILN-style), mono face for telemetry and ASCII, and Noto families for content in each script: Noto Sans Bengali, Noto Sans Devanagari, Noto Sans Kannada, Noto Sans JP. Check every script renders with proper line height and shaping in transcripts, buttons and the Studio.
- Radii, blur levels, glass opacity, glow strengths, easing curves, durations: defined as CSS variables and GSAP defaults in one file.
- Spacing scale and a 12-column grid with oversized type allowed to bleed.

## 4. Motion language

From the Zajno guide: consistent easing curves, staggered entrances, morph between shapes, masked content inside morphing containers, parallax depth, zoom transitions. Rules:
- 3 easing curves only (enter, exit, emphasis) and 3 durations.
- Every page has one signature moment, the rest is restrained.
- Scroll storytelling on Landing only. App pages respond to interaction and voice, not scroll tricks.
- Optional sound feedback (hover/click) off by default.

## 5. Technology

- GSAP (ScrollTrigger, SplitText, MorphSVG): GSAP's standard license says it is free for everyone, including formerly paid plugins, with commercial use allowed. Restrictions include no use in no-code tools that compete with Webflow's visual animation builder, no reverse engineering, and Webflow can change the license. ShaOn is not a no-code animation tool. Pin the GSAP version and re-read the license at release.
- Lenis (smooth scroll) and Motion/Framer Motion for UI micro-interactions. Check licenses when installing.
- three.js with React Three Fiber for the voice orb, particles and wave field. Custom GLSL for shaders.
- ASCII art, two techniques:
  1. three.js `AsciiEffect`: renders the scene to a character grid in a DOM element. Likely limitations (summary from general knowledge, check the three.js docs/source): CPU pixel readback is slow at high resolution, output is DOM text, needs a monospace font, and is not screen-reader friendly. Use for small decorative panels only.
  2. Custom GPU ASCII post-process shader (glyph atlas, brightness-mapped) for the full-screen hero. Preferred.
  ASCII glyphs are Latin and symbols only. Never render Bengali, Devanagari, Kannada or Japanese through the ASCII pipeline; real language content always renders as normal DOM text with Noto fonts.
- Unicorn Studio: has a free plan, a feature for live embeds, and an embed guide at unicorn.studio/docs/embed/. The page does not state export or watermark rules or performance guidance (not verified; it names Vue 3 and curtains.js in its stack). Use it for the landing backdrop only if the embed works in Next.js, shows no watermark on the free plan, and holds frame rate. Otherwise build the backdrop in R3F.
- Web Audio `AnalyserNode` on mic and agent playback feeds amplitude and frequency bands to shader uniforms.
- Icons: simple line icons; avoid generic stock look.

## 6. Voice-reactive visual system ("the Signal")

States, each with a distinct motion: idle (slow drift), listening (reacts to mic level), thinking (contracting, rotating filaments), speaking (reacts to agent audio, bands map to ASCII density), language switch (particles morph from one language glyph motif to another, Halovane-style), handoff (calm, desaturated), error (brief interrupt, never alarming).
Per-language identity: hue plus a glyph motif and ASCII wordmark variant (Latin-rendered language names in the ASCII layer, native script names in DOM text beside it).
Input signals: mic level, playback level, current language, state, pointer position (Kreivo-style visitor control).

## 7. Pages and signature moments

- Landing: oversized type, shader or particle hero reacting to pointer, ASCII wordmark assembling from particles, scroll-driven reveal into a "how it works" technical story (Immersive Robotics idea), preset gallery with spatial browsing (DNA Carousel / basement idea), liquid-metal "Start a demo" button.
- App shell: capsule top nav and expandable dock (Supaste, Sable, Glass Portfolio ideas), animated active states.
- Agent Studio: oversized section headings, glass panels, tab transitions with masked morphs (Zajno idea), live preview of the agent's greeting with the selected voice, guardrail chips with micro-animations.
- Live Call: full-bleed Signal visual, transcript as a floating glass column with language badges, latency as a minimal telemetry strip in mono type, voice switcher as a dock.
- Knowledge: URL drop zone that reacts to drag, crawl progress as a scroll/graph transformation (ARQ-01 idea): pages appear as nodes that fill in, then collapse into the brief.
- Call Logs: dense, calm, mono telemetry; replay a call with the Signal re-driven from stored timings.

## 8. Performance and the GPU conflict

The STT/TTS models and the web visuals may share one GPU. Rules:
- Effects tiers: Auto, Full, Lite, Off. Auto picks from measured frame rate. Live Call defaults to Lite while models are generating (cap device pixel ratio, cap at 30 fps, reduce particle count).
- Pause all heavy animation when the tab is hidden or the user is not on a visual page.
- Budgets (targets): 60 fps desktop on Full for the landing hero, 30 fps during calls on Lite, first contentful content fast on landing (lazy-load 3D after text).
- Test visuals WHILE OmniVoice/Parler and Whisper are running, not just alone. Verify that visuals do not add noticeable delay to time-to-first-audio.
- Compress images (AVIF/WebP variants exist from your assets). Lazy-load video.

## 9. Accessibility

- `prefers-reduced-motion`: swap to static or minimal motion, keep state indicators.
- Real text transcript always in DOM (ASCII is decorative with `aria-hidden`).
- Keyboard navigation for all controls, visible focus, sufficient contrast, no flashing faster than 3 per second.
- Captions are the transcript with language badges.
- Fonts: test Bengali, Devanagari, Kannada and Japanese rendering at all sizes.

## 10. Design milestones

- D0: tokens, fonts for 5 scripts, Landing hero and Live Call Signal prototype with real audio levels, performance check while models run.
- D1: shell, dock/capsule nav, Studio layout.
- D2: Knowledge and Logs pages, motion polish, ASCII layer.
- D3: tiers, reduced-motion, accessibility, visual regression screenshots (Playwright), Lighthouse pass, final art pass against the Folded Signal moodboard.

Definition of done for design: each page has its signature moment, runs in all three effect tiers, passes the accessibility list, and a screenshot set is stored in `design/screens/`.
