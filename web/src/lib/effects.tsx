"use client";
/**
 * Effects tiers (DESIGN.md section 8): Auto | Full | Lite | Off.
 * - Auto measures frame rate for ~2 s and picks Full / Lite / Off.
 * - prefers-reduced-motion forces Off (static visuals, state indicators kept).
 * - While models are generating on the Live Call page, Auto drops to Lite (setGenerating).
 * - Heavy animation pauses when the tab is hidden.
 * The choice is a per-viewer convenience kept in localStorage (wrapped in try/catch).
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type TierChoice = "auto" | "full" | "lite" | "off";
export type Tier = "full" | "lite" | "off";

type Ctx = {
  choice: TierChoice;
  tier: Tier;
  measuredFps: number | null;
  reducedMotion: boolean;
  hidden: boolean;
  generating: boolean;
  /** WebGL runs on the CPU (SwiftShader / llvmpipe): the orb competes with the speech models for the same cores */
  software: boolean;
  setChoice: (c: TierChoice) => void;
  setGenerating: (g: boolean) => void;
};

const EffectsContext = createContext<Ctx | null>(null);

/** True when WebGL runs on the CPU (SwiftShader / llvmpipe): visuals would compete with the speech models. */
export function softwareRenderer(): boolean {
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl") || c.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) return true;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const r = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    return /swiftshader|llvmpipe|software|softpipe/i.test(r);
  } catch { return false; }
}
const KEY = "shaon.effects";

function readChoice(): TierChoice {
  try {
    const url = new URL(window.location.href).searchParams.get("effects");
    if (url === "auto" || url === "full" || url === "lite" || url === "off") return url;
    const v = window.localStorage.getItem(KEY);
    if (v === "auto" || v === "full" || v === "lite" || v === "off") return v;
  } catch {}
  return "auto";
}

export function EffectsProvider({ children }: { children: React.ReactNode }) {
  const [choice, setChoiceState] = useState<TierChoice>("auto");
  const [measuredFps, setFps] = useState<number | null>(null);
  const [reducedMotion, setRM] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [software, setSoftware] = useState(false);
  const [phone, setPhone] = useState(false);

  useEffect(() => {
    setChoiceState(readChoice());
    setSoftware(softwareRenderer());
    setPhone(window.matchMedia("(pointer: coarse)").matches || window.innerWidth < 768);
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setRM(mq.matches);
    const onMq = () => setRM(mq.matches);
    mq.addEventListener("change", onMq);
    const onVis = () => setHidden(document.visibilityState === "hidden");
    document.addEventListener("visibilitychange", onVis);
    return () => { mq.removeEventListener("change", onMq); document.removeEventListener("visibilitychange", onVis); };
  }, []);

  // FPS probe for Auto (runs once, 2 seconds)
  useEffect(() => {
    if (choice !== "auto" || measuredFps !== null) return;
    let frames = 0, raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      frames++;
      if (t - start < 2000) raf = requestAnimationFrame(tick);
      else setFps(Math.round((frames * 1000) / (t - start)));
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [choice, measuredFps]);

  const tier: Tier = useMemo(() => {
    if (reducedMotion) return "off";
    if (choice !== "auto") return choice;
    let t: Tier = measuredFps === null ? "lite" : measuredFps >= 50 ? "full" : measuredFps >= 24 ? "lite" : "off";
    if ((generating || software || phone) && t === "full") t = "lite"; // design/perf.md; phones default to Lite
    return t;
  }, [choice, measuredFps, reducedMotion, generating, software, phone]);

  useEffect(() => {
    document.documentElement.dataset.effects = tier;
    import("gsap").then(({ default: gsap }) => gsap.globalTimeline.timeScale(tier === "off" ? 1000 : 1)); // off/reduced: end states, no motion
  }, [tier]);

  const setChoice = useCallback((c: TierChoice) => {
    setChoiceState(c);
    try { window.localStorage.setItem(KEY, c); } catch {}
  }, []);

  const value = { choice, tier, measuredFps, reducedMotion, hidden, generating, software, setChoice, setGenerating };
  return <EffectsContext.Provider value={value}>{children}</EffectsContext.Provider>;
}

export function useEffectsTier(): Ctx {
  const c = useContext(EffectsContext);
  if (!c) throw new Error("useEffectsTier outside EffectsProvider");
  return c;
}

export function EffectsPicker({ compact = false }: { compact?: boolean }) {
  const { choice, tier, setChoice, measuredFps, reducedMotion } = useEffectsTier();
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Visual effects">
      {!compact && <span className="telemetry">Effects</span>}
      <div className="seg">
        {(["auto", "full", "lite", "off"] as TierChoice[]).map((c) => (
          <button key={c} type="button" aria-pressed={c === choice} onClick={() => setChoice(c)}>{c}</button>
        ))}
      </div>
      <span className="telemetry" aria-live="polite" data-testid="fps">
        {reducedMotion ? "reduced motion" : `${tier}${measuredFps ? ` · ${measuredFps} fps` : ""}`}
      </span>
    </div>
  );
}
