"use client";
import { useEffect, useRef } from "react";
import { LANG_NAMES, type Lang } from "@/lib/tokens";

export type Line = { id: number; role: "user" | "agent" | "system"; text: string; lang?: Lang; meta?: string; handoff?: boolean;
  sources?: { url: string; title?: string }[]; guard?: string; demoVoice?: boolean };

export function Transcript({ lines }: { lines: Line[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [lines.length]);
  return (
    <div className="flex flex-col gap-3 overflow-y-auto pr-1" style={{ maxHeight: "min(62vh, 640px)" }} aria-live="polite" aria-label="Call transcript" data-testid="transcript">
      {lines.length === 0 && <p className="telemetry">Transcript appears here. Captions = transcript with language badges.</p>}
      {lines.map((l) => (
        <div key={l.id} className="fade-in" data-role={l.role} data-lang={l.lang}>
          <div className="flex items-center gap-2 mb-1">
            <span className="telemetry">{l.role === "user" ? "Caller" : l.role === "agent" ? "Agent" : "System"}</span>
            {l.lang && <span className={`lang-badge lang-${l.lang}`} title={LANG_NAMES[l.lang]?.latin}>{l.lang.toUpperCase()}</span>}
            {l.handoff && <span className="badge-demo">handoff</span>}
            {l.guard && <span className="badge-demo" style={{ color: "var(--danger)" }}>guardrail: {l.guard}</span>}
            {l.demoVoice && <span className="badge-demo">demo-only voice</span>}
            {l.meta && <span className="telemetry" style={{ textTransform: "none" }}>{l.meta}</span>}
          </div>
          <p lang={l.lang} className="text-[15px]" style={{ color: l.role === "system" ? "var(--ink-muted)" : "var(--ink)" }}>{l.text}</p>
          {l.sources && l.sources.length > 0 && (
            <p className="telemetry mt-1" style={{ textTransform: "none" }}>sources: {l.sources.map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noreferrer" className="underline mr-2">{s.title || s.url}</a>))}</p>
          )}
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}
