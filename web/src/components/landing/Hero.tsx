"use client";
/**
 * Landing hero: headline with a live waveform glyph (Audigo idea), the interactive SignalStage on the right and a
 * SIMULATED demo controller (states, language, ASCII/particles). The demo cycles by itself until the visitor takes
 * control; it never touches the microphone and is labelled "Simulated".
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { emptyLevels, type Levels, type SignalState } from "@/components/signal/Signal";
import { SignalStage, useSimulatedLevels } from "@/components/signal/SignalStage";
import type { Motif } from "@/components/signal/motifs";
import { EffectsPicker } from "@/lib/effects";
import { LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

const DEMO: { s: SignalState; label: string }[] = [
  { s: "idle", label: "Idle" }, { s: "listening", label: "Listen" }, { s: "thinking", label: "Think" },
  { s: "speaking", label: "Speak" }, { s: "switch", label: "Switch" }, { s: "error", label: "Error" },
];
const SCRIPT = ["listening", "thinking", "speaking", "switch", "listening", "speaking", "idle"] as SignalState[];

export function Hero() {
  const [state, setState] = useState<SignalState>("idle");
  const [lang, setLang] = useState<Lang>("en");
  const [ascii, setAscii] = useState(true);
  const [motif, setMotif] = useState<Motif | undefined>("word");
  const [auto, setAuto] = useState(true);
  const levels = useRef<Levels>(emptyLevels());
  useSimulatedLevels(levels, state);

  // wordmark first, then the language motif; then a scripted demo loop until the visitor interacts
  useEffect(() => {
    // reduced motion / Off tier: no self-changing content, the visitor drives the demo
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.effects === "off") setAuto(false);
    const t = window.setTimeout(() => setMotif(undefined), 2600);
    return () => window.clearTimeout(t);
  }, []);
  useEffect(() => {
    if (!auto) return;
    let i = 0;
    const id = window.setInterval(() => {
      const s = SCRIPT[i % SCRIPT.length];
      if (s === "switch") setLang((l) => LANGS[(LANGS.indexOf(l) + 1) % LANGS.length]);
      setState(s);
      i++;
    }, 2400);
    return () => window.clearInterval(id);
  }, [auto]);
  const take = () => setAuto(false);
  const pickState = (s: SignalState) => {
    take();
    if (s === "switch") setLang((l) => LANGS[(LANGS.indexOf(l) + 1) % LANGS.length]);
    setState(s);
  };

  return (
    <section className="relative overflow-hidden" aria-labelledby="hero-title" style={{ minHeight: "calc(100svh - var(--topbar-h))" }}>
      <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] items-center mx-auto"
        style={{ maxWidth: "var(--content-max)", padding: "clamp(28px, 6vh, 72px) var(--gutter) 32px" }}>
        <div className="min-w-0 order-2 lg:order-1">
          <p className="kicker"><span className="faint">00 </span>Local multilingual voice agents</p>
          <h1 id="hero-title" className="display mt-5" style={{ fontSize: "clamp(34px, 4.7vw, 78px)" }}>
            <span className="block">A signal that</span>
            <span className="block">listens <Wave levelsRef={levels} /></span>
            <span className="block">in <span style={{ color: `var(--lang-${lang})`, transition: "color var(--dur-slow) var(--ease-enter)" }}>five</span> scripts.</span>
          </h1>
          <p className="page-sub mt-6">
            Configure a phone-style support agent, point it at your own website and talk to it in English, 日本語, हिन्दी, বাংলা
            or ಕನ್ನಡ. Speech runs on this PC; only text goes to Claude.
          </p>
          <div className="flex flex-wrap items-center gap-3 mt-8">
            <Link href="/call/" className="btn btn-primary btn-lg" data-testid="hero-call">Start a live call <span className="arrow">→</span></Link>
            <Link href="/studio/" className="btn btn-lg">Configure an agent</Link>
          </div>
          <dl className="grid grid-cols-2 md:grid-cols-4 mt-10" style={{ borderTop: "1px solid var(--line)" }}>
            {[["05", "languages, native script"], ["CPU", "speech runs on this PC"], ["3–6 s", "first audio, measured on CPU"], ["0", "keys sent to the browser"]].map(([v, k], i) => (
              <div key={k} className="py-4 pr-3" style={{ borderRight: i % 2 === 0 ? "1px solid var(--line)" : undefined, paddingLeft: i % 2 ? 14 : 0 }}>
                <dt className="sr-only">{k}</dt>
                <dd className="m-0"><span className="display block" style={{ fontSize: 28 }}>{v}</span><span className="telemetry" style={{ fontSize: 10 }}>{k}</span></dd>
              </div>))}
          </dl>
        </div>

        <div className="contents lg:block min-w-0 lg:order-2">
          <SignalStage state={state} lang={lang} levelsRef={levels} motif={motif} ascii={ascii} simulated className="w-full max-w-[640px] mx-auto order-1 lg:order-none" testid="hero-stage" />
          <div className="module mt-4 order-3 lg:order-none" data-testid="demo-controls" onPointerDown={take}>
            <div className="module-head"><span className={`light ${auto ? "light-live" : "light-ok"}`} /><span className="ttl">Simulated demo</span>
              <span className="spacer" /><span>{auto ? "auto" : "manual"}</span></div>
            <div className="module-body grid gap-3">
              <div className="seg" role="group" aria-label="Orb state (simulated)">
                {DEMO.map((d) => <button key={d.s} type="button" aria-pressed={state === d.s} onClick={() => pickState(d.s)}>{d.label}</button>)}
              </div>
              <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Language motif">
                {LANGS.map((l) => (
                  <button key={l} type="button" lang={l} className={`btn btn-sm lang-${l}`} aria-pressed={lang === l}
                    style={{ borderColor: lang === l ? "currentColor" : undefined, fontFamily: `var(--font-${l === "en" ? "body" : l})` }}
                    onClick={() => { take(); setLang(l); setState("switch"); }}>{LANG_NAMES[l].native}</button>))}
              </div>
              <div className="flex flex-wrap items-center gap-3 justify-between">
                <div className="seg" role="group" aria-label="Render mode">
                  <button type="button" aria-pressed={ascii} onClick={() => { take(); setAscii(true); }}>ASCII</button>
                  <button type="button" aria-pressed={!ascii} onClick={() => { take(); setAscii(false); }}>Particles</button>
                </div>
                <EffectsPicker compact />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Inline waveform glyph inside the headline, driven by the (simulated) levels. Decorative. */
function Wave({ levelsRef }: { levelsRef: React.RefObject<Levels> }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let raf = 0;
    const bars = ref.current ? Array.from(ref.current.children) as HTMLElement[] : [];
    const tick = (t: number) => {
      const L = levelsRef.current, base = Math.max(L?.mic ?? 0, L?.out ?? 0);
      bars.forEach((b, i) => {
        const v = 0.18 + Math.abs(Math.sin(t / 260 + i * 0.9)) * 0.3 + base * (0.5 + 0.5 * Math.sin(t / 90 + i * 1.7));
        b.style.transform = `scaleY(${Math.min(1, v).toFixed(3)})`;
      });
      raf = requestAnimationFrame(tick);
    };
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && document.documentElement.dataset.effects !== "off") raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [levelsRef]);
  return (
    <span ref={ref} aria-hidden="true" className="inline-flex items-center gap-[0.06em] align-middle" style={{ height: "0.7em", margin: "0 0.08em" }}>
      {Array.from({ length: 9 }, (_, i) => (
        <span key={i} style={{ display: "block", width: "0.07em", height: "100%", background: "var(--signal)", borderRadius: 2, transform: "scaleY(0.4)", transformOrigin: "center" }} />
      ))}
    </span>
  );
}
