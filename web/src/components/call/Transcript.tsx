"use client";
/** Call transcript: the captions. Native script as DOM text with the right Noto font; role rail colours; sources. */
import { useEffect, useRef } from "react";
import { LANG_NAMES, type Lang } from "@/lib/tokens";

export type Line = { id: number; role: "user" | "agent" | "system"; text: string; lang?: Lang; meta?: string; handoff?: boolean;
  sources?: { url: string; title?: string }[]; guard?: string; demoVoice?: boolean };

const RAIL = { user: "var(--signal-alt)", agent: "var(--signal)", system: "var(--line-strong)" };

export function Transcript({ lines }: { lines: Line[] }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { const b = box.current; if (b) b.scrollTop = b.scrollHeight; }, [lines.length]);
  return (
    <div ref={box} className="flex flex-col gap-3 overflow-y-auto pr-1" style={{ maxHeight: "min(52vh, 560px)", minHeight: 120 }}
      aria-live="polite" aria-label="Call transcript" data-testid="transcript">
      {lines.length === 0 && (
        <div className="empty">
          <span className="ascii faint" aria-hidden="true" style={{ fontSize: 12 }}>{"[ . . . waiting for a caller . . . ]"}</span>
          <span className="text-sm">Captions appear here: every turn, in the caller&apos;s own script, with its language.</span>
        </div>)}
      {lines.map((l) => (
        <div key={l.id} className="fade-in" data-role={l.role} data-lang={l.lang}
          style={{ borderLeft: `2px solid ${RAIL[l.role]}`, paddingLeft: 12, opacity: l.role === "system" ? 0.85 : 1 }}>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="telemetry" style={{ color: l.role === "system" ? undefined : RAIL[l.role] }}>{l.role === "user" ? "Caller" : l.role === "agent" ? "Agent" : "System"}</span>
            {l.lang && <span className={`lang-badge lang-${l.lang}`} title={LANG_NAMES[l.lang]?.latin}>{l.lang.toUpperCase()}</span>}
            {l.handoff && <span className="chip chip-warn">handoff</span>}
            {l.guard && <span className="chip chip-danger">guardrail: {l.guard}</span>}
            {l.demoVoice && <span className="chip chip-warn">demo-only voice</span>}
            {l.meta && <span className="telemetry" style={{ textTransform: "none", letterSpacing: 0 }}>{l.meta}</span>}
          </div>
          <p lang={l.lang} style={{ fontSize: l.role === "system" ? 13 : 16, lineHeight: 1.55, color: l.role === "system" ? "var(--ink-muted)" : "var(--ink)" }}>{l.text}</p>
          {l.sources && l.sources.length > 0 && (
            <p className="telemetry mt-1" style={{ textTransform: "none", letterSpacing: 0 }}>sources: {l.sources.map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noreferrer" className="underline mr-2">{s.title || s.url}</a>))}</p>
          )}
        </div>
      ))}
    </div>
  );
}
