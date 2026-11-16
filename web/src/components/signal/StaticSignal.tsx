"use client";
/** Effects "off" / reduced-motion version of the Signal: static, state still visible. */
import type { Lang } from "@/lib/tokens";
import type { SignalState } from "./Signal";

export function StaticSignal({ state, lang, className }: { state: SignalState; lang: Lang; className?: string }) {
  const ring = state === "handoff" ? "var(--ink-faint)" : state === "error" ? "var(--warn)" : `var(--lang-${lang})`;
  const scale = state === "thinking" ? 0.8 : state === "speaking" || state === "listening" ? 1.05 : 1;
  return (
    <div className={className} aria-hidden="true" data-testid="signal" data-state={state} data-tier="off"
      style={{ display: "grid", placeItems: "center" }}>
      <div style={{
        width: "min(60vmin, 420px)", aspectRatio: "1", borderRadius: "50%", transform: `scale(${scale})`,
        background: `radial-gradient(circle at 50% 45%, color-mix(in srgb, ${ring} 55%, transparent), transparent 62%)`,
        boxShadow: `0 0 0 1px color-mix(in srgb, ${ring} 40%, transparent) inset`,
      }} />
    </div>
  );
}
