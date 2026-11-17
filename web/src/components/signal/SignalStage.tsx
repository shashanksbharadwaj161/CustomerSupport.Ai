"use client";
/**
 * SignalStage: the orb as an instrument (design/references.md). The particle Signal sits inside a measuring reticle
 * (SVG) with live call-outs; every state has its own reticle behaviour:
 *   idle = slow tick drift · listening = cyan ticks swell with the mic · thinking = violet sweep + counter-rotating
 *   dashes · speaking = acid level arc follows playback · switch = ring flashes in the new language hue ·
 *   handoff = calm, desaturated · error = one red pulse (never flashing faster than 3/s).
 * Interaction: drag (or arrow keys) rotates the orb, +/- zooms, R or double-click resets. Live numbers are written by
 * requestAnimationFrame straight into the DOM (no React re-render per frame). Off tier / reduced motion: static.
 * Language names are DOM text (native script); the ASCII layer stays Latin/symbols only.
 */
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { useEffectsTier } from "@/lib/effects";
import { LANG_NAMES, type Lang } from "@/lib/tokens";
import { emptyControl, type Control, type Levels, type SignalState } from "./Signal";
import type { Motif } from "./motifs";

const Signal = dynamic(() => import("./Signal").then((m) => m.Signal), { ssr: false });

const STATE_LABEL: Record<SignalState, string> = {
  idle: "Idle", listening: "Listening", thinking: "Thinking", speaking: "Speaking", switch: "Switching language",
  handoff: "Handing off", error: "Error",
};
const STATE_COLOR: Record<SignalState, string> = {
  idle: "var(--ink-muted)", listening: "var(--signal-alt)", thinking: "var(--think)", speaking: "var(--signal)",
  switch: "var(--signal)", handoff: "var(--ink-faint)", error: "var(--danger)",
};

type Props = {
  state: SignalState;
  lang: Lang;
  levelsRef: React.RefObject<Levels>;
  motif?: Motif;
  ascii?: boolean;
  /** shown on the stage when the levels are synthetic (landing demo) */
  simulated?: boolean;
  className?: string;
  /** compact = fewer call-outs (phones, small panels) */
  compact?: boolean;
  testid?: string;
};

export function SignalStage({ state, lang, levelsRef, motif, ascii, simulated, className = "", compact, testid = "signal-stage" }: Props) {
  const { tier } = useEffectsTier();
  const control = useRef<Control>(emptyControl());
  const box = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);
  const [hint, setHint] = useState(true);
  const still = tier === "off";

  // live call-outs + reticle variables: one rAF, writes CSS vars and text only
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    let raf = 0, t0 = performance.now();
    const mic = el.querySelector<HTMLElement>("[data-v=mic]"), out = el.querySelector<HTMLElement>("[data-v=out]");
    const yaw = el.querySelector<HTMLElement>("[data-v=yaw]");
    const arc = el.querySelector<SVGCircleElement>("[data-v=arc]");
    const C = 2 * Math.PI * 41;
    const tick = (t: number) => {
      const L = levelsRef.current;
      const m = L?.mic ?? 0, o = L?.out ?? 0;
      el.style.setProperty("--lvl-mic", m.toFixed(3));
      el.style.setProperty("--lvl-out", o.toFixed(3));
      if (!still) el.style.setProperty("--spin", `${((t - t0) / 1000) * (state === "thinking" ? 40 : state === "handoff" ? 2 : 6)}deg`);
      if (mic) mic.textContent = m > 0.001 ? `${(20 * Math.log10(Math.max(m, 1e-4))).toFixed(1)} dB` : "-- dB";
      if (out) out.textContent = o.toFixed(2);
      if (arc) arc.style.strokeDasharray = `${(C * Math.min(1, (state === "speaking" ? o : m) * 1.4)).toFixed(1)} ${C.toFixed(1)}`;
      if (yaw) yaw.textContent = `${Math.round((control.current.yaw * 180) / Math.PI) % 360}°`;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [levelsRef, state, still]);

  const onDown = (e: React.PointerEvent) => {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, yaw: control.current.yaw, pitch: control.current.pitch };
    setHint(false);
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    control.current.yaw = d.yaw + (e.clientX - d.x) * 0.01;
    control.current.pitch = Math.max(-1.1, Math.min(1.1, d.pitch + (e.clientY - d.y) * 0.01));
  };
  const onUp = () => { drag.current = null; };
  const reset = useCallback(() => { control.current = emptyControl(); }, []);
  const onKey = (e: React.KeyboardEvent) => {
    const c = control.current, step = 0.15;
    const k = e.key;
    if (k === "ArrowLeft") c.yaw -= step; else if (k === "ArrowRight") c.yaw += step;
    else if (k === "ArrowUp") c.pitch = Math.max(-1.1, c.pitch - step); else if (k === "ArrowDown") c.pitch = Math.min(1.1, c.pitch + step);
    else if (k === "+" || k === "=") c.zoom = Math.min(1.6, c.zoom + 0.1); else if (k === "-" || k === "_") c.zoom = Math.max(0.6, c.zoom - 0.1);
    else if (k === "r" || k === "R" || k === "0") reset();
    else return;
    e.preventDefault(); setHint(false);
  };

  const color = state === "switch" ? `var(--lang-${lang})` : STATE_COLOR[state];
  return (
    <div ref={box} className={`relative select-none ${className}`} data-testid={testid} data-state={state} data-lang={lang}
      style={{ ["--st" as string]: color, aspectRatio: "1 / 1", touchAction: "none", cursor: drag.current ? "grabbing" : "grab" }}
      tabIndex={0} role="group" aria-roledescription="interactive orb"
      aria-label={`Signal orb, state ${STATE_LABEL[state]}, language ${LANG_NAMES[lang].latin}. Drag or use arrow keys to rotate, plus and minus to zoom, R to reset.`}
      onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onDoubleClick={reset} onKeyDown={onKey}>
      <Signal state={state} lang={lang} levelsRef={levelsRef} motif={motif} ascii={ascii} controlRef={control} className="absolute inset-[9%]" />
      <Reticle state={state} still={still} />
      {/* call-outs: DOM text at the corners, never over the orb centre */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <Callout pos="tl" k="State"><span style={{ color }} data-testid="stage-state">{STATE_LABEL[state]}</span></Callout>
        <Callout pos="tr" k="Lang"><span lang={lang} style={{ color: `var(--lang-${lang})`, fontFamily: `var(--font-${lang === "en" ? "body" : lang})` }}>{LANG_NAMES[lang].native}</span></Callout>
        {!compact && <Callout pos="bl" k="Mic"><span className="num" data-v="mic">-- dB</span></Callout>}
        {!compact && <Callout pos="br" k="Out"><span className="num" data-v="out">0.00</span></Callout>}
      </div>
      {simulated && <span className="chip chip-warn absolute pointer-events-none" style={{ left: "50%", bottom: compact ? 2 : 10, transform: "translateX(-50%)" }}>Simulated demo · no audio</span>}
      {hint && !still && (
        <span className="telemetry absolute pointer-events-none hidden md:block" style={{ left: "50%", top: 6, transform: "translateX(-50%)", fontSize: 10 }}>
          Drag to rotate · <span className="num" data-v="yaw">0°</span>
        </span>
      )}
    </div>
  );
}

function Callout({ pos, k, children }: { pos: "tl" | "tr" | "bl" | "br"; k: string; children: React.ReactNode }) {
  const s: React.CSSProperties = { position: "absolute", display: "flex", flexDirection: "column", gap: 2, maxWidth: "40%" };
  if (pos[0] === "t") s.top = "3%"; else s.bottom = "3%";
  if (pos[1] === "l") { s.left = "1%"; } else { s.right = "1%"; s.alignItems = "flex-end"; s.textAlign = "right"; }
  return (
    <div style={s}>
      <span className="telemetry" style={{ fontSize: 10 }}>{k}</span>
      <span style={{ fontSize: 14, fontWeight: 500 }}>{children}</span>
    </div>
  );
}

/** Measuring reticle. CSS variables --spin, --lvl-mic, --lvl-out and --st (state colour) drive it. */
function Reticle({ state, still }: { state: SignalState; still: boolean }) {
  const ticks = Array.from({ length: 96 }, (_, i) => i);
  const listening = state === "listening", thinking = state === "thinking", speaking = state === "speaking";
  const C = 2 * Math.PI * 41;
  return (
    <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true" style={{ overflow: "visible" }}>
      {/* crosshair with a gap around the orb */}
      <g stroke="var(--line-strong)" strokeWidth="0.15">
        <line x1="0" y1="50" x2="6" y2="50" /><line x1="94" y1="50" x2="100" y2="50" />
        <line x1="50" y1="0" x2="50" y2="6" /><line x1="50" y1="94" x2="50" y2="100" />
      </g>
      {/* dimension line (technical-drawing ornament) */}
      <g stroke="var(--line-strong)" strokeWidth="0.15" fill="none">
        <path d="M9 96.5 H91 M9 95.5 v2 M91 95.5 v2" />
      </g>
      <text x="9" y="99.4" textAnchor="start" fontSize="1.9" fill="var(--ink-faint)" fontFamily="var(--font-mono)">Ø 82.0</text>
      {/* tick ring */}
      <g style={{ transformOrigin: "50px 50px", transform: still ? undefined : `rotate(var(--spin)) scale(calc(1 + var(--lvl-mic, 0) * ${listening ? 0.07 : 0}))`,
        transition: "stroke var(--dur-base) var(--ease-enter)" }} stroke="var(--st)" strokeWidth="0.25">
        {ticks.map((i) => {
          const a = (i / ticks.length) * Math.PI * 2, long = i % 8 === 0;
          const r1 = 45.5, r2 = long ? 48 : 46.6;
          return <line key={i} x1={50 + Math.cos(a) * r1} y1={50 + Math.sin(a) * r1} x2={50 + Math.cos(a) * r2} y2={50 + Math.sin(a) * r2}
            opacity={long ? 0.9 : 0.45} />;
        })}
      </g>
      {/* inner orbit: dashed, counter-rotates while thinking */}
      <circle cx="50" cy="50" r="43.2" fill="none" stroke="var(--st)" strokeWidth="0.18" strokeDasharray={thinking ? "1.2 2.2" : "0.4 3"}
        opacity={state === "handoff" ? 0.3 : 0.6} style={{ transformOrigin: "50px 50px", transform: still ? undefined : `rotate(calc(var(--spin) * -1.6))` }} />
      {/* thinking sweep */}
      {thinking && !still && (
        <path d="M50 50 L50 8.8 A41.2 41.2 0 0 1 79.1 20.9 Z" fill="url(#sweep)" style={{ transformOrigin: "50px 50px", transform: "rotate(calc(var(--spin) * 3))" }} />
      )}
      {/* speaking: level arc follows playback; listening: mic arc */}
      {(speaking || listening) && (
        <circle data-v="arc" cx="50" cy="50" r="41" fill="none" stroke={speaking ? "var(--signal)" : "var(--signal-alt)"} strokeWidth="0.7" strokeLinecap="round"
          strokeDasharray={`0 ${C}`} transform="rotate(-90 50 50)" />
      )}
      {state === "error" && <circle cx="50" cy="50" r="44" fill="none" stroke="var(--danger)" strokeWidth="0.5" className="reticle-pulse" />}
      <defs>
        <radialGradient id="sweep" cx="50" cy="50" r="42" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--think)" stopOpacity="0" /><stop offset="1" stopColor="var(--think)" stopOpacity="0.28" />
        </radialGradient>
      </defs>
    </svg>
  );
}

/** Synthetic levels for the landing demo (clearly labelled "Simulated"): no microphone, no audio. */
export function useSimulatedLevels(levelsRef: React.RefObject<Levels>, state: SignalState, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    let raf = 0;
    const tick = (t: number) => {
      const L = levelsRef.current;
      if (L) {
        const s = t / 1000;
        const syll = Math.max(0, Math.sin(s * 7.3) * Math.sin(s * 2.1 + 1) * 0.9 + Math.sin(s * 17) * 0.1);
        L.mic = state === "listening" ? 0.15 + syll * 0.65 : 0.02;
        L.out = state === "speaking" ? 0.12 + syll * 0.7 : 0;
        L.bands = state === "speaking" ? [syll, syll * 0.8 + 0.1 * Math.sin(s * 9), syll * 0.6, syll * 0.35] : [0, 0, 0, 0];
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [levelsRef, state, enabled]);
}
