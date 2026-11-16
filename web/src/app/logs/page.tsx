"use client";
/** Call Logs: dense, calm telemetry. Detail = transcript + per-turn timings + guardrail events + Signal replay. */
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { emptyLevels, type Levels, type SignalState } from "@/components/signal/Signal";
import { api } from "@/lib/api";
import type { Lang } from "@/lib/tokens";

const Signal = dynamic(() => import("@/components/signal/Signal").then((m) => m.Signal), { ssr: false });

type Call = { id: string; profile_id: string; transport: string; started_at: number; ended_at: number | null; languages_used: string | null;
  provider: string; turns: number; guard_events: number; active: boolean };
type Turn = { id: number; role: string; language: Lang; text: string; stt_ms: number | null; llm_ms: number | null; llm_ttft_ms: number | null;
  guard_ms: number | null; tts_ms: number | null; first_audio_ms: number | null; lang_reason: string | null; engine: any; sources: any; guardrail: any; created_at: number };

const fmtT = (t: number) => new Date(t * 1000).toLocaleString();
const ms = (v: number | null | undefined) => (v == null ? "-" : `${v}`);

export default function Logs() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [id, setId] = useState<string | null>(null);
  const [d, setD] = useState<{ call: Call; turns: Turn[]; guardrail_events: any[] } | null>(null);
  useEffect(() => {
    api<Call[]>("/api/calls").then(setCalls).catch(() => {});
    try { setId(new URL(window.location.href).searchParams.get("id")); } catch {}
  }, []);
  useEffect(() => { if (id) api(`/api/calls/${id}`).then(setD as any).catch(() => setD(null)); }, [id]);

  if (id && d) return <AppShell><Detail d={d} /></AppShell>;
  const avg = (xs: number[]) => (xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null);
  return (
    <AppShell>
      <h1 className="display my-6" style={{ fontSize: "clamp(40px, 7vw, 104px)" }}>Call Logs</h1>
      <div className="glass overflow-x-auto">
        <table className="w-full mono text-xs" data-testid="calls-table">
          <thead><tr className="telemetry text-left">{["started", "call", "agent", "transport", "languages", "llm", "turns", "guard", ""].map((h) => <th key={h} className="px-3 py-2">{h}</th>)}</tr></thead>
          <tbody>{calls.map((c) => (
            <tr key={c.id} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="px-3 py-2 whitespace-nowrap">{fmtT(c.started_at)}</td><td className="px-3">{c.id}</td><td className="px-3">{c.profile_id}</td>
              <td className="px-3">{c.transport}</td><td className="px-3">{c.languages_used || "-"}</td><td className="px-3">{c.provider}</td>
              <td className="px-3">{c.turns}</td><td className="px-3" style={{ color: c.guard_events ? "var(--warn)" : undefined }}>{c.guard_events}</td>
              <td className="px-3"><Link className="underline" href={`/logs/?id=${c.id}`} onClick={() => setId(c.id)}>{c.active ? "live" : "open"}</Link></td>
            </tr>))}
            {calls.length === 0 && <tr><td className="px-3 py-6" colSpan={9}>No calls yet. Start one on the Live Call page.</td></tr>}</tbody>
        </table>
      </div>
    </AppShell>
  );

  function Detail({ d }: { d: { call: Call; turns: Turn[]; guardrail_events: any[] } }) {
    const fa = d.turns.map((t) => t.first_audio_ms).filter((x): x is number => x != null);
    return (
      <div className="space-y-6 my-6" data-testid="call-detail">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><Link href="/logs/" className="telemetry underline" onClick={() => { setId(null); setD(null); }}>← all calls</Link>
            <h1 className="display text-4xl mt-2">{d.call.id}</h1>
            <p className="telemetry">{fmtT(d.call.started_at)} · {d.call.transport} · {d.call.provider} · languages {d.call.languages_used || "-"} · avg first audio {avg(fa) ?? "-"} ms</p></div>
        </div>
        <Replay turns={d.turns} />
        <div className="glass overflow-x-auto">
          <table className="w-full text-xs" data-testid="turns-table">
            <thead><tr className="telemetry text-left">{["role", "lang", "text", "reason", "stt", "llm 1st", "llm", "guard", "tts", "first audio"].map((h) => <th key={h} className="px-3 py-2">{h}</th>)}</tr></thead>
            <tbody>{d.turns.map((t) => (
              <tr key={t.id} className="border-t align-top" style={{ borderColor: "var(--line)" }}>
                <td className="px-3 py-2 mono">{t.role}</td><td className="px-3"><span className={`lang-badge lang-${t.language}`}>{t.language}</span></td>
                <td className="px-3 py-2 max-w-[44ch]" lang={t.language}>{t.text}{t.sources?.length ? <div className="telemetry mt-1" style={{ textTransform: "none" }}>sources: {t.sources.map((s: any) => s.title).join(", ")}</div> : null}</td>
                <td className="px-3 mono">{t.lang_reason || "-"}</td>
                {[t.stt_ms, t.llm_ttft_ms, t.llm_ms, t.guard_ms, t.tts_ms, t.first_audio_ms].map((v, i) => <td key={i} className="px-3 mono">{ms(v)}</td>)}
              </tr>))}</tbody>
          </table>
        </div>
        <div className="glass p-4"><h2 className="telemetry mb-2">Guardrail events ({d.guardrail_events.length})</h2>
          <ul className="mono text-xs space-y-1">{d.guardrail_events.map((g) => <li key={g.id}>{g.stage} · {g.verdict} · {g.rule} · {g.detail}</li>)}</ul></div>
      </div>
    );
  }
}

/** Re-drive the Signal from stored timings: listening = caller audio length, thinking = STT + LLM first text, speaking = estimate. */
function Replay({ turns }: { turns: Turn[] }) {
  const [state, setState] = useState<SignalState>("idle");
  const [lang, setLang] = useState<Lang>("en");
  const [label, setLabel] = useState("ready");
  const levels = useRef<Levels>(emptyLevels());
  const timers = useRef<number[]>([]);
  function play() {
    timers.current.forEach(clearTimeout); timers.current = [];
    let t = 0;
    const at = (dt: number, f: () => void) => { t += dt; timers.current.push(window.setTimeout(f, t)); };
    for (let i = 0; i < turns.length; i++) {
      const u = turns[i];
      if (u.role === "user") {
        const listen = Math.round((u.engine?.audio_s ?? 2) * 1000);
        at(0, () => { setState("listening"); setLang(u.language); setLabel(`caller · ${u.language} · ${listen} ms speech`); levels.current.mic = 0.6; });
        const a = turns[i + 1];
        at(listen, () => { setState("thinking"); levels.current.mic = 0; setLabel(`thinking · stt ${ms(u.stt_ms)} · llm 1st ${ms(a?.llm_ttft_ms)} ms`); });
        const think = (a?.first_audio_ms ?? (u.stt_ms ?? 0) + (a?.llm_ms ?? 0));
        at(Math.max(300, think), () => { setState("speaking"); setLang(a?.language ?? u.language); setLabel(`agent · first audio ${ms(a?.first_audio_ms)} ms`); levels.current.out = 0.5; levels.current.bands = [0.5, 0.4, 0.3, 0.2]; });
        at(Math.min(8000, Math.max(1200, (a?.text?.length ?? 40) * 60)), () => { setState("idle"); levels.current = emptyLevels(); setLabel("idle (speaking length estimated from text)"); });
      }
    }
  }
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  return (
    <div className="glass relative h-[320px] overflow-hidden">
      <Signal state={state} lang={lang} levelsRef={levels} className="absolute inset-0" />
      <div className="absolute left-4 bottom-4 flex items-center gap-3">
        <button className="btn" onClick={play} data-testid="replay">Replay call</button>
        <span className="telemetry" aria-live="polite">{label}</span>
      </div>
    </div>
  );
}
