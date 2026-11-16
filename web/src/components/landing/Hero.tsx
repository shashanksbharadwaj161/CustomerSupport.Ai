"use client";
/** Landing hero: particles assemble into an ASCII wordmark (GPU ASCII pass), pointer-reactive. */
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { emptyLevels, type Levels } from "@/components/signal/Signal";
import { EffectsPicker } from "@/lib/effects";
import { gsap, setupMotion } from "@/lib/motion";
import { LANG_NAMES, LANGS, token, type Lang } from "@/lib/tokens";
import type { Motif } from "@/components/signal/motifs";

// three.js loads after the text (DESIGN.md section 8: lazy-load 3D after text)
const Signal = dynamic(() => import("@/components/signal/Signal").then((m) => m.Signal), { ssr: false });

export function Hero() {
  const [lang, setLang] = useState<Lang>("en");
  const [motif, setMotif] = useState<Motif>("sphere");
  const levels = useRef<Levels>(emptyLevels());
  const title = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    setupMotion();
    const t = window.setTimeout(() => setMotif("word"), 900); // wordmark assembles from particles
    const id = window.setInterval(() => setLang((l) => LANGS[(LANGS.indexOf(l) + 1) % LANGS.length]), 3200);
    if (title.current) {
      gsap.from(title.current.querySelectorAll("[data-line]"), { yPercent: 110, opacity: 0, stagger: 0.08, duration: token.dur("slow") });
    }
    return () => { window.clearTimeout(t); window.clearInterval(id); };
  }, []);

  return (
    <section className="relative overflow-hidden" style={{ minHeight: "100svh" }} aria-labelledby="hero-title">
      <Signal state="idle" lang={lang} motif={motif} ascii levelsRef={levels} className="absolute inset-0" />
      <div className="relative z-10 flex flex-col justify-end min-h-[100svh]" style={{ padding: "96px var(--gutter) 40px", pointerEvents: "none" }}>
        <p className="telemetry mb-4">Local multilingual voice agents · demo build</p>
        <h1 id="hero-title" ref={title} className="display" style={{ fontSize: "clamp(44px, 9vw, 150px)", maxWidth: "14ch" }}>
          <span className="block overflow-hidden" style={{ paddingBottom: "0.14em", marginBottom: "-0.14em" }}><span data-line className="block">A signal that</span></span>
          <span className="block overflow-hidden" style={{ paddingBottom: "0.14em", marginBottom: "-0.14em" }}><span data-line className="block">listens in <span style={{ color: `var(--lang-${lang})`, transition: "color var(--dur-slow) var(--ease-enter)" }}>five</span></span></span>
          <span className="block overflow-hidden" style={{ paddingBottom: "0.14em", marginBottom: "-0.14em" }}><span data-line className="block">languages.</span></span>
        </h1>
        <ul className="flex flex-wrap gap-3 mt-6" aria-label="Supported languages">
          {LANGS.map((l) => (
            <li key={l} lang={l} className={`lang-badge lang-${l}`} style={{ fontFamily: "var(--font-body)", fontSize: 14, opacity: l === lang ? 1 : 0.55 }}>
              {LANG_NAMES[l].native}
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center gap-4 mt-8" style={{ pointerEvents: "auto" }}>
          <Link href="/call/" className="btn btn-metal" style={{ padding: "14px 28px", fontSize: 16 }}>Start a demo</Link>
          <Link href="/studio/" className="btn">Configure an agent</Link>
          <EffectsPicker compact />
        </div>
      </div>
    </section>
  );
}
