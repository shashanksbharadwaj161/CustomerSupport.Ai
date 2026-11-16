"use client";
/** Scroll-driven technical story (Immersive Robotics idea, re-implemented): one pinned stage, five steps. */
import { useEffect, useRef } from "react";
import { useEffectsTier } from "@/lib/effects";
import { gsap, ScrollTrigger, setupMotion } from "@/lib/motion";

const STEPS = [
  { k: "01", t: "Listens", d: "Voice activity detection cuts your speech into turns, locally. Audio never leaves the machine.", m: "VAD · SMART TURN" },
  { k: "02", t: "Identifies the language", d: "Language ID over five candidates, biased to the previous turn, double-checked by the script of the transcript.", m: "LID · SCRIPT CHECK" },
  { k: "03", t: "Understands", d: "Speech to text per language: Whisper for English and Japanese, IndicConformer for Hindi, Bengali, Kannada (GPU).", m: "STT ROUTER" },
  { k: "04", t: "Answers from your site", d: "Claude Haiku 5.5 answers only from your crawled website, retrieved passages and tools. Guardrails check every sentence.", m: "RAG · GUARDRAILS" },
  { k: "05", t: "Speaks back", d: "Reply language is read from the reply's script; the matching voice speaks it, sentence by sentence.", m: "TTS ROUTER" },
];

export function HowItWorks() {
  const root = useRef<HTMLDivElement>(null);
  const { tier } = useEffectsTier();
  useEffect(() => {
    if (tier === "off" || !root.current) return;
    setupMotion();
    const ctx = gsap.context(() => {
      const panels = gsap.utils.toArray<HTMLElement>("[data-step]");
      const tl = gsap.timeline({ scrollTrigger: { trigger: root.current, start: "top top", end: `+=${panels.length * 70}%`, scrub: 0.6, pin: true } });
      // cross-fade: step i+1 starts entering before step i has left, so one step is always readable
      panels.forEach((p, i) => {
        if (i > 0) tl.fromTo(p, { yPercent: 30, opacity: 0, clipPath: "inset(30% 0 30% 0)" },
          { yPercent: 0, opacity: 1, clipPath: "inset(0% 0 0% 0)", ease: "emphasis", duration: 0.45 }, i - 0.25);
        if (i < panels.length - 1) tl.to(p, { yPercent: -25, opacity: 0, ease: "exit", duration: 0.4 }, i + 0.75);
      });
      tl.fromTo("[data-progress]", { scaleX: 0 }, { scaleX: 1, ease: "none", duration: panels.length }, 0);
    }, root);
    return () => { ctx.revert(); ScrollTrigger.refresh(); };
  }, [tier]);

  if (tier === "off") {
    return (
      <section aria-labelledby="how-h" className="px-[var(--gutter)] py-24 max-w-[var(--content-max)] mx-auto">
        <h2 id="how-h" className="display mb-10" style={{ fontSize: "clamp(36px, 6vw, 88px)" }}>How ShaOn works</h2>
        <ol className="grid gap-6 md:grid-cols-5">{STEPS.map((s) => (
          <li key={s.k} className="glass p-5"><p className="telemetry">{s.k} · {s.m}</p><h3 className="display text-2xl my-2">{s.t}</h3><p className="text-sm" style={{ color: "var(--ink-muted)" }}>{s.d}</p></li>))}</ol>
      </section>
    );
  }
  return (
    <section ref={root} aria-labelledby="how-h" className="relative h-[100svh] overflow-hidden">
      <div className="absolute inset-0 grid place-items-center px-[var(--gutter)]">
        <h2 id="how-h" className="sr-only">How ShaOn works</h2>
        <div className="relative w-full max-w-[var(--content-max)] h-[60vh]">
          {STEPS.map((s, i) => (
            <article key={s.k} data-step className="absolute inset-0 grid md:grid-cols-[1fr_1.2fr] gap-8 items-center" style={{ opacity: i === 0 ? 1 : 0 }} aria-label={`Step ${s.k}: ${s.t}`}>
              <div className="display" style={{ fontSize: "clamp(96px, 20vw, 320px)", color: "transparent", WebkitTextStroke: "1px var(--line-strong)" }} aria-hidden="true">{s.k}</div>
              <div>
                <p className="telemetry mb-3" style={{ color: "var(--signal)" }}>{s.m}</p>
                <h3 className="display mb-4" style={{ fontSize: "clamp(36px, 5vw, 80px)" }}>{s.t}</h3>
                <p className="text-lg max-w-[42ch]" style={{ color: "var(--ink-muted)" }}>{s.d}</p>
              </div>
            </article>))}
        </div>
        <div className="absolute bottom-10 inset-x-[var(--gutter)] h-px" style={{ background: "var(--line)" }}>
          <div data-progress className="h-px origin-left" style={{ background: "var(--signal)" }} />
        </div>
      </div>
    </section>
  );
}
