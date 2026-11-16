"use client";
/** Live Call: full-bleed Signal, floating transcript, telemetry strip, voice dock, language override. */
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { Transcript, type Line } from "@/components/call/Transcript";
import { AppShell } from "@/components/shell/AppShell";
import { emptyLevels, type Levels, type SignalState } from "@/components/signal/Signal";
import { api } from "@/lib/api";
import { driveLevels, LevelMeter } from "@/lib/audio";
import { WebRTCCall } from "@/lib/call/webrtc";
import { WebSocketCall } from "@/lib/call/websocket";
import type { CallClient, ServerMsg, TransportKind } from "@/lib/call/types";
import { EffectsPicker, useEffectsTier } from "@/lib/effects";
import { LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

const Signal = dynamic(() => import("@/components/signal/Signal").then((m) => m.Signal), { ssr: false });

type Profile = { id: string; name: string; type: string };
type Voice = { id: string; language: Lang; display_name: string; engine: string; demo_only?: boolean; status?: string };
type TurnTiming = { turn_id?: number; stt_ms?: number; lid_ms?: number; llm_ttft_ms?: number; llm_ms?: number; guard_ms?: number;
  tts_ms?: number; first_audio_ms?: number; client_first_audio_ms?: number; tier?: string };

declare global { interface Window { __shaon?: { turns: TurnTiming[]; messages: ServerMsg[]; state: string } } }

function defaultTransport(): TransportKind {
  try {
    const q = new URL(window.location.href).searchParams.get("transport");
    if (q === "websocket" || q === "ws") return "websocket";
    if (q === "smallwebrtc" || q === "webrtc") return "smallwebrtc";
    return ["localhost", "127.0.0.1"].includes(window.location.hostname) ? "smallwebrtc" : "websocket";
  } catch { return "smallwebrtc"; }
}

export default function LiveCall() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [transport, setTransport] = useState<TransportKind>("smallwebrtc");
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "ended" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<SignalState>("idle");
  const [lang, setLang] = useState<Lang>("en");
  const [override, setOverride] = useState<Lang | "">("");
  const [lines, setLines] = useState<Line[]>([]);
  const [timing, setTiming] = useState<TurnTiming>({});
  const [voices, setVoices] = useState<Voice[]>([]);
  const [activeVoice, setActiveVoice] = useState<Record<string, string>>({});
  const [info, setInfo] = useState<{ provider?: string; languages?: Lang[] }>({});
  const client = useRef<CallClient | null>(null);
  const levels = useRef<Levels>(emptyLevels());
  const stopLevels = useRef<() => void>(() => {});
  const lineId = useRef(0);
  const tThinking = useRef<number | null>(null);
  const { tier, setGenerating } = useEffectsTier();
  const tierRef = useRef(tier);
  tierRef.current = tier;

  useEffect(() => {
    setTransport(defaultTransport());
    window.__shaon = { turns: [], messages: [], state: "idle" };
    api<Profile[]>("/api/profiles").then((p) => {
      setProfiles(p);
      const q = new URL(window.location.href).searchParams.get("profile");
      setProfileId(q && p.some((x) => x.id === q) ? q : p[0]?.id ?? null);
    }).catch(() => {});
    api<Voice[]>("/api/voices").then(setVoices).catch(() => setVoices([]));
  }, []);

  useEffect(() => { setGenerating(state === "thinking" || state === "speaking"); }, [state, setGenerating]);
  useEffect(() => () => { client.current?.disconnect(); stopLevels.current(); setGenerating(false); }, [setGenerating]);

  const add = useCallback((l: Omit<Line, "id">) => setLines((xs) => [...xs, { ...l, id: ++lineId.current }]), []);

  const onMsg = useCallback((m: ServerMsg) => {
    window.__shaon?.messages.push(m);
    switch (m.event) {
      case "hello":
        setInfo({ provider: m.provider, languages: m.languages }); setLang(m.lang); setActiveVoice(m.voices || {}); break;
      case "state":
        if (m.state === "thinking") tThinking.current = performance.now();
        if (m.state === "speaking" && tThinking.current) {
          const c = Math.round(performance.now() - tThinking.current); tThinking.current = null;
          setTiming((t) => ({ ...t, client_first_audio_ms: c }));
        }
        setState(m.state === "idle" ? "idle" : m.state);
        if (window.__shaon) window.__shaon.state = m.state;
        break;
      case "transcript":
        if (m.lang && m.lang !== lang) { setState("switch"); }
        if (m.lang) setLang(m.lang);
        add({ role: m.role, text: m.text, lang: m.lang, handoff: m.handoff,
          meta: m.role === "user" ? [m.reason, m.stt_ms != null ? `stt ${m.stt_ms} ms` : null].filter(Boolean).join(" · ") : undefined });
        break;
      case "sources":
        setLines((xs) => { const c = [...xs]; for (let i = c.length - 1; i >= 0; i--) if (c[i].role === "user") { c[i] = { ...c[i] }; break; } return c; });
        add({ role: "system", text: `Retrieved ${m.sources.length} passage(s)`, sources: m.sources }); break;
      case "guardrail":
        add({ role: "system", text: `Guardrail ${m.action}: ${m.rule}${m.detail ? ` (${m.detail})` : ""}`, guard: m.rule }); break;
      case "tts":
        setLines((xs) => { const c = [...xs]; const i = c.map((x) => x.role).lastIndexOf("agent"); if (i >= 0 && m.demo_only) c[i] = { ...c[i], demoVoice: true }; return c; });
        break;
      case "tts_unavailable":
        add({ role: "system", text: `No speech voice for ${m.lang?.toUpperCase()} on this machine yet: text only. ${m.detail}` }); break;
      case "turn_meta":
        setTiming((t) => ({ ...t, turn_id: m.turn_id, stt_ms: m.stt_ms, lid_ms: m.lid_ms, llm_ttft_ms: m.llm_ttft_ms, llm_ms: m.llm_ms, guard_ms: m.guard_ms }));
        break;
      case "latency":
        setTiming((t) => {
          const n = { ...t, first_audio_ms: m.first_audio_ms, tts_ms: m.tts_ms, tier: tierRef.current };
          window.__shaon?.turns.push(n);
          return n;
        }); break;
      case "voice": setActiveVoice((v) => ({ ...v, [m.lang]: m.voice })); break;
      case "error": add({ role: "system", text: `Error in ${m.stage}: ${m.detail}` }); setState("error"); break;
      case "interrupted": add({ role: "system", text: "Caller interrupted (barge-in)" }); break;
    }
  }, [add, lang]);

  async function start() {
    setError(null); setLines([]); setStatus("connecting"); setTiming({});
    const c: CallClient = transport === "websocket" ? new WebSocketCall(profileId) : new WebRTCCall(profileId);
    c.onMessage = onMsg;
    c.onClose = (r) => { setStatus((s) => (s === "live" || s === "connecting" ? "ended" : s)); setState("idle"); if (r !== "ended") setError(`Connection ${r}`); };
    client.current = c;
    try {
      await c.connect();
      setStatus("live");
      const wire = () => {
        const mi = c.micNode(), ou = c.outNode();
        stopLevels.current();
        stopLevels.current = driveLevels(levels, mi ? new LevelMeter(mi.ctx, mi.node) : null, ou ? new LevelMeter(ou.ctx, ou.node) : null);
        return !!ou;
      };
      if (!wire()) { const id = window.setInterval(() => { if (wire()) window.clearInterval(id); }, 500); window.setTimeout(() => window.clearInterval(id), 10000); }
    } catch (e: any) {
      setStatus("error"); setError(e?.message || String(e)); c.disconnect();
    }
  }
  function end() { client.current?.disconnect(); client.current = null; stopLevels.current(); setStatus("ended"); setState("idle"); }

  function setOverrideLang(l: Lang | "") { setOverride(l); client.current?.send({ type: "override_lang", lang: l || null }); }
  function pickVoice(l: Lang, v: string) { client.current?.send({ type: "set_voice", lang: l, voice: v }); setActiveVoice((x) => ({ ...x, [l]: v })); }

  const live = status === "live";
  const langVoices = voices.filter((v) => v.language === lang);

  return (
    <AppShell wide>
      <div className="relative grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <section className="relative min-h-[60vh] lg:min-h-[78vh]" aria-label="Voice visual">
          <Signal state={state} lang={lang} levelsRef={levels} className="absolute inset-0" />
          <div className="absolute left-0 top-0 flex flex-wrap items-center gap-2">
            <span className={`lang-badge lang-${lang}`} lang={lang} data-testid="current-lang" style={{ fontFamily: "var(--font-body)", fontSize: 14 }}>{LANG_NAMES[lang].native}</span>
            <span className="telemetry" data-testid="call-state">{status} · {state}</span>
          </div>
          {/* telemetry strip */}
          <div className="absolute inset-x-0 bottom-0 glass px-4 py-2 flex flex-wrap gap-x-5 gap-y-1 mono text-[11px]" data-testid="telemetry" style={{ borderRadius: "var(--radius-md)" }}>
            <span>transport {transport}</span>
            <span>llm {info.provider ?? "-"}</span>
            <span>stt {timing.stt_ms ?? "-"} ms</span>
            <span>lid {timing.lid_ms ?? "-"} ms</span>
            <span>llm first text {timing.llm_ttft_ms ?? "-"} ms</span>
            <span>guard {timing.guard_ms ?? "-"} ms</span>
            <span>tts gen {timing.tts_ms ?? "-"} ms</span>
            <span style={{ color: "var(--signal)" }}>first audio {timing.first_audio_ms ?? "-"} ms</span>
            <span>effects {tier}</span>
          </div>
        </section>
        <aside className="glass p-4 flex flex-col gap-4" aria-label="Call controls and transcript">
          <div className="flex flex-wrap gap-2 items-end">
            <label className="flex flex-col gap-1 text-sm">Agent
              <select className="btn" value={profileId ?? ""} onChange={(e) => setProfileId(e.target.value)} disabled={live} data-testid="profile-select">
                {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select></label>
            <label className="flex flex-col gap-1 text-sm">Transport
              <select className="btn" value={transport} onChange={(e) => setTransport(e.target.value as TransportKind)} disabled={live}>
                <option value="smallwebrtc">WebRTC (local)</option><option value="websocket">WebSocket (tunnel)</option>
              </select></label>
            {!live ? <button className="btn btn-metal" onClick={start} disabled={status === "connecting" || !profileId} data-testid="start-call">{status === "connecting" ? "Connecting…" : "Start call"}</button>
              : <button className="btn" style={{ borderColor: "var(--danger)", color: "var(--danger)" }} onClick={end} data-testid="end-call">End call</button>}
          </div>
          {error && <p role="alert" className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}
          <Transcript lines={lines} />
          <div className="mt-auto space-y-3">
            <label className="flex items-center gap-2 text-sm">Language override
              <select className="btn" value={override} onChange={(e) => setOverrideLang(e.target.value as Lang | "")} data-testid="override">
                <option value="">auto</option>
                {(info.languages || LANGS).map((l) => <option key={l} value={l}>{LANG_NAMES[l].native}</option>)}
              </select></label>
            <div role="group" aria-label={`Voices for ${LANG_NAMES[lang].latin}`} className="flex flex-wrap gap-2" data-testid="voice-dock">
              {langVoices.map((v) => (
                <button key={v.id} className="btn" style={{ padding: "4px 10px", fontSize: 12, borderColor: activeVoice[lang] === v.id ? "var(--signal)" : undefined }}
                  aria-pressed={activeVoice[lang] === v.id} disabled={!live} onClick={() => pickVoice(lang, v.id)}
                  title={v.status === "pending" ? "PENDING: engine not verified on this machine" : v.engine}>
                  {v.display_name}{v.demo_only ? " · demo" : ""}{v.status === "pending" ? " · pending" : ""}
                </button>))}
            </div>
            <EffectsPicker compact />
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
