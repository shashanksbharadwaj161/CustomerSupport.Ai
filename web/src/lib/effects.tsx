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
  setChoice: (c: TierChoice) => void;
  setGenerating: (g: boolean) => void;
};

const EffectsContext = createContext<Ctx | null>(null);
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

  useEffect(() => {
    setChoiceState(readChoice());
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
    if (generating && t === "full") t = "lite";
    return t;
  }, [choice, measuredFps, reducedMotion, generating]);

  useEffect(() => { document.documentElement.dataset.effects = tier; }, [tier]);

  const setChoice = useCallback((c: TierChoice) => {
    setChoiceState(c);
    try { window.localStorage.setItem(KEY, c); } catch {}
  }, []);

  const value = { choice, tier, measuredFps, reducedMotion, hidden, generating, setChoice, setGenerating };
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
    <div className="flex items-center gap-2" role="group" aria-label="Visual effects">
      {!compact && <span className="telemetry">Effects</span>}
      {(["auto", "full", "lite", "off"] as TierChoice[]).map((c) => (
        <button key={c} type="button" className="btn" style={{ padding: "4px 10px", fontSize: 12, borderColor: c === choice ? "var(--signal)" : undefined }}
          aria-pressed={c === choice} onClick={() => setChoice(c)}>{c}</button>
      ))}
      <span className="telemetry" aria-live="polite">
        {reducedMotion ? "reduced motion" : `${tier}${measuredFps ? ` · ${measuredFps} fps` : ""}`}
      </span>
    </div>
  );
}
