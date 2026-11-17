"use client";
/** Live Call console: the SignalStage reacts to the real mic / playback levels; transcript, telemetry and controls
 *  sit in modules around it (never on top of it). */
import { useCallback, useEffect, useRef, useState } from "react";
import { DemoBanner, GetReady, useReady } from "@/components/call/GetReady";
import { Transcript, type Line } from "@/components/call/Transcript";
import { AppShell, Module } from "@/components/shell/AppShell";
import { IconMic, IconStop } from "@/components/shell/Icons";
import { emptyLevels, type Levels, type SignalState } from "@/components/signal/Signal";
import { SignalStage } from "@/components/signal/SignalStage";
import { api, ApiError } from "@/lib/api";
import { driveLevels, LevelMeter } from "@/lib/audio";
import { WebRTCCall } from "@/lib/call/webrtc";
import { WebSocketCall } from "@/lib/call/websocket";
import type { CallClient, ServerMsg, TransportKind } from "@/lib/call/types";
import { useEffectsTier } from "@/lib/effects";
import { humanDuration, LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

type Profile = { id: string; name: string; type: string };
type Voice = { id: string; language: Lang; display_name: string; engine: string; demo_only?: boolean; status?: string };
type TurnTiming = { turn_id?: number; stt_ms?: number; lid_ms?: number; llm_ttft_ms?: number; llm_ms?: number; guard_ms?: number;
  tts_ms?: number; first_audio_ms?: number; client_first_audio_ms?: number; tier?: string; model?: string; model_served?: string; model_fallback?: string };

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
  const [screen, setScreen] = useState<null | { kind: "busy" | "ended" | "lost"; text: string }>(null);
  const { ready } = useReady();
  const userEnded = useRef(false);
  const missedBeats = useRef(0);
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

  // heartbeat while live: if the host PC disappears (sleep, offline, tunnel restarted) show a friendly state, not a blank screen
  useEffect(() => {
    if (status !== "live") return;
    const id = window.setInterval(async () => {
      try { const r = await fetch("/health", { cache: "no-store" }); missedBeats.current = r.ok ? 0 : missedBeats.current + 1; }
      catch { missedBeats.current += 1; }
      if (missedBeats.current >= 2) {
        userEnded.current = true; client.current?.disconnect(); setStatus("ended"); setState("idle");
        setScreen({ kind: "lost", text: "The host PC stopped answering (asleep, offline, or the share link changed). Try again in a moment, or ask for a new link." });
      }
    }, 5000);
    return () => window.clearInterval(id);
  }, [status]);

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
        setTiming((t) => ({ ...t, turn_id: m.turn_id, stt_ms: m.stt_ms, lid_ms: m.lid_ms, llm_ttft_ms: m.llm_ttft_ms, llm_ms: m.llm_ms, guard_ms: m.guard_ms,
          model: (m as any).model, model_served: (m as any).model_served, model_fallback: (m as any).model_fallback }));
        break;
      case "latency":
        setTiming((t) => {
          const n = { ...t, first_audio_ms: m.first_audio_ms, tts_ms: m.tts_ms, tier: tierRef.current };
          window.__shaon?.turns.push(n);
          return n;
        }); break;
      case "voice": setActiveVoice((v) => ({ ...v, [m.lang]: m.voice })); break;
      case "error": add({ role: "system", text: `Error in ${m.stage}: ${m.detail}` }); setState("error"); break;
      case "busy": setScreen({ kind: "busy", text: "The agent is busy with another caller right now. Please try again in a minute." }); break;
      case "ended":
        userEnded.current = true;
        setScreen({ kind: "ended", text: m.reason === "max_length" ? `The call ended automatically after ${humanDuration(m.seconds || 300)} (demo time limit). You can start a new call.` : "The call has ended." });
        break;
      case "interrupted": add({ role: "system", text: "Caller interrupted (barge-in)" }); break;
    }
  }, [add, lang]);

  async function start() {
    setError(null); setLines([]); setStatus("connecting"); setTiming({}); setScreen(null); userEnded.current = false; missedBeats.current = 0;
    const c: CallClient = transport === "websocket" ? new WebSocketCall(profileId) : new WebRTCCall(profileId);
    c.onMessage = onMsg;
    c.onClose = (r) => {
      setStatus((s) => (s === "live" || s === "connecting" ? "ended" : s)); setState("idle");
      if (r === "ended" || userEnded.current) return;
      setScreen((cur) => cur ?? (r.includes("4503") ? { kind: "busy", text: "The agent is busy with another caller right now. Please try again in a minute." }
        : r.includes("4429") ? { kind: "busy", text: "Too many call attempts from your network in the last minute. Please wait a minute, then try again." }
        : r.includes("4401") ? { kind: "lost", text: "Your passcode session expired. Reload the page and enter the passcode again." }
        : { kind: "lost", text: "The connection was lost. The host PC may have gone to sleep, lost its internet, or the share link changed. Try again in a moment, or ask for a new link." }));
    };
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
      userEnded.current = true; c.disconnect(); setStatus("error");
      if (e instanceof ApiError && e.status === 429) setScreen({ kind: "busy", text: "Too many call attempts from your network in the last minute. Please wait a minute, then try again." });
      else if (e instanceof ApiError && e.status === 503) setScreen({ kind: "busy", text: "The agent is busy with another caller right now. Please try again in a minute." });
      else if (e?.name === "NotAllowedError") setError("Microphone permission was blocked. Allow it in the browser's site settings, then try again.");
      else if (e?.name === "NotFoundError" || e?.name === "OverconstrainedError") setError("No microphone was found. Plug one in (or pick it in Windows sound settings), then press Start call again.");
      else if (e?.name === "NotReadableError" || e?.name === "AbortError") setError("The microphone is busy or blocked by another app (or Windows privacy settings). Close the other app, then try again.");
      else if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setError("Your passcode session expired. Reload the page and enter the passcode again.");
      else setScreen({ kind: "lost", text: "Could not reach the agent. The host PC may be offline or the link may have changed." });
    }
  }
  function end() { userEnded.current = true; client.current?.disconnect(); client.current = null; stopLevels.current(); setStatus("ended"); setState("idle"); }

  function setOverrideLang(l: Lang | "") { setOverride(l); client.current?.send({ type: "override_lang", lang: l || null }); }
  function pickVoice(l: Lang, v: string) { client.current?.send({ type: "set_voice", lang: l, voice: v }); setActiveVoice((x) => ({ ...x, [l]: v })); }

  const live = status === "live";
  const langVoices = voices.filter((v) => v.language === lang && v.status !== "pending"); // only voices that can speak on this machine

  const callLabel = status === "connecting" ? "Connecting" : live ? "Live" : status === "ended" ? "Ended" : status === "error" ? "Not connected" : "Ready";
  return (
    <AppShell wide reasons={false}>
      <div className="mx-auto" style={{ maxWidth: 1480 }}>
        {/* control bar */}
        <div className="flex flex-wrap items-end gap-3 pt-5 pb-4" style={{ borderBottom: "1px solid var(--line)" }}>
          <div className="mr-auto min-w-0">
            <p className="kicker"><span className="faint">01 </span>Live call</p>
            <h1 className="headline mt-1" style={{ fontSize: "clamp(26px, 3.2vw, 40px)" }}>
              <span className={`light ${live ? "light-live" : status === "error" ? "light-danger" : "light-ok"}`} style={{ display: "inline-block", marginRight: 12, verticalAlign: "middle" }} />
              <span data-testid="call-state">{callLabel}</span><span className="faint" style={{ fontWeight: 400 }}> · {state}</span>
            </h1>
          </div>
          <label className={`label ${live ? "hidden sm:flex" : ""}`} style={{ minWidth: 220, flex: "1 1 220px", maxWidth: 320 }}>Agent
            <select value={profileId ?? ""} onChange={(e) => setProfileId(e.target.value)} disabled={live} data-testid="profile-select">
              {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select></label>
          <label className={`label ${live ? "hidden sm:flex" : ""}`} style={{ minWidth: 170, flex: "0 1 190px" }}>Transport
            <select value={transport} onChange={(e) => setTransport(e.target.value as TransportKind)} disabled={live}>
              <option value="smallwebrtc">WebRTC (this PC)</option><option value="websocket">WebSocket (link)</option>
            </select></label>
          {!live ? <button className="btn btn-primary btn-lg" onClick={start} disabled={status === "connecting" || !profileId} data-testid="start-call"><IconMic />{status === "connecting" ? "Connecting…" : "Start call"}</button>
            : <button className="btn btn-danger btn-lg" onClick={end} data-testid="end-call"><IconStop />End call</button>}
        </div>
        <div className="my-4"><DemoBanner ready={ready} /></div>
        {error && <p role="alert" className="notice notice-danger mb-4">{error}</p>}
        {screen && (
          <div role="alertdialog" aria-labelledby="screen-h" className={`notice ${screen.kind === "lost" ? "notice-danger" : "notice-warn"} mb-4 flex-wrap items-center`} data-testid={`screen-${screen.kind}`}>
            <div className="flex-1 min-w-[220px]"><h2 id="screen-h" className="headline mb-1" style={{ fontSize: 20, color: "var(--ink)" }}>{screen.kind === "busy" ? "Agent is busy" : screen.kind === "ended" ? "Call ended" : "Connection lost"}</h2>
              <p style={{ color: "var(--ink)" }}>{screen.text}</p></div>
            <button className="btn btn-primary" onClick={() => { setScreen(null); start(); }} data-testid="screen-retry">{screen.kind === "ended" ? "New call" : "Try again"} <span className="arrow">→</span></button>
          </div>)}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(340px,440px)] items-start">
          {/* stage + telemetry */}
          <div className="contents lg:grid gap-4 min-w-0">
            <section className="hud relative overflow-hidden p-3 md:p-6 order-1 lg:order-none" aria-label="Voice visual" style={{ ["--tick-c" as string]: live ? "var(--signal)" : "var(--line-strong)" }}>
              <SignalStage state={state} lang={lang} levelsRef={levels} className="w-full mx-auto max-w-[min(640px,70vh)]" compact={false} testid="call-stage" />
            </section>
            <Module index="T" title="Telemetry" className="order-5 lg:order-none" light={timing.first_audio_ms ? "ok" : "off"} testid="telemetry"
              actions={<span>{transport} · {info.provider ?? "llm -"} · fx {tier}</span>}>
              <Latency timing={timing} />
              <dl className="rows mt-4">
                <dt>Model</dt><dd className="mono" style={{ fontSize: 13 }}>{timing.model_served || timing.model || (info.provider === "anthropic" ? "first reply pending" : info.provider ? `${info.provider} (no Claude call)` : "-")}
                  {timing.model_fallback && <span className="chip chip-warn ml-2">fallback: {timing.model_fallback}</span>}</dd>
                <dt>Client</dt><dd className="num" style={{ fontSize: 13 }}>{timing.client_first_audio_ms != null ? `${timing.client_first_audio_ms} ms thinking → speaking (browser clock)` : "-"}</dd>
              </dl>
            </Module>
          </div>

          {/* right column: get ready / transcript / controls */}
          <div className="contents lg:grid gap-4 min-w-0">
            {!live && status !== "connecting" && <div className="order-2 lg:order-none"><GetReady ready={ready} canStart={!!profileId} onStart={start} /></div>}
            <Module index="C" title="Transcript" className="order-3 lg:order-none" light={live ? "live" : lines.length ? "ok" : "off"} actions={<span>{lines.length} lines</span>}>
              <Transcript lines={lines} />
            </Module>
            <Module index="V" title="Language & voice" className="order-4 lg:order-none">
              <div className="grid gap-4">
                <div>
                  <p className="label mb-2">Language override</p>
                  <div className="seg" role="radiogroup" aria-label="Language override" data-testid="override">
                    <button type="button" role="radio" aria-checked={override === ""} onClick={() => setOverrideLang("")}>Auto</button>
                    {(info.languages || LANGS).map((l) => (
                      <button key={l} type="button" role="radio" aria-checked={override === l} lang={l} onClick={() => setOverrideLang(l)}
                        style={{ fontFamily: `var(--font-${l === "en" ? "body" : l})`, textTransform: "none", letterSpacing: 0, fontSize: 13 }}>{LANG_NAMES[l].native}</button>))}
                  </div>
                  <p className="hint mt-2">Auto follows the caller&apos;s language each turn. An override always wins.</p>
                </div>
                <div>
                  <p className="label mb-2">Voice for {LANG_NAMES[lang].native}</p>
                  <div role="group" aria-label={`Voices for ${LANG_NAMES[lang].latin}`} className="flex flex-wrap gap-2" data-testid="voice-dock">
                    {langVoices.length === 0 && <span className="hint">No voice installed for this language.</span>}
                    {langVoices.map((v) => (
                      <button key={v.id} className="btn btn-sm" aria-pressed={activeVoice[lang] === v.id} disabled={!live} onClick={() => pickVoice(lang, v.id)}
                        title={v.engine}>{v.display_name}{v.demo_only ? " · demo" : ""}</button>))}
                  </div>
                  {!live && langVoices.length > 0 && <p className="hint mt-2">Voices switch live during a call (from the next sentence).</p>}
                </div>
              </div>
            </Module>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

const LAT: { k: keyof TurnTiming; label: string }[] = [
  { k: "stt_ms", label: "Speech → text" }, { k: "lid_ms", label: "Language ID" }, { k: "llm_ttft_ms", label: "Claude first text" },
  { k: "guard_ms", label: "Guard check" }, { k: "tts_ms", label: "Voice gen" }, { k: "first_audio_ms", label: "First audio" },
];
function Latency({ timing }: { timing: TurnTiming }) {
  const max = Math.max(3000, ...LAT.map((x) => Number(timing[x.k]) || 0));
  return (
    <ul className="grid gap-2" aria-label="Latency of the last turn, milliseconds">
      {LAT.map((x) => {
        const v = timing[x.k] as number | undefined, first = x.k === "first_audio_ms";
        return (
          <li key={x.k} className="grid grid-cols-[120px_1fr_70px] sm:grid-cols-[150px_1fr_80px] items-center gap-3">
            <span className="telemetry" style={{ fontSize: 10, color: first ? "var(--signal)" : undefined }}>{x.label}</span>
            <span className="meter"><span style={{ width: `${v ? Math.max(2, (v / max) * 100) : 0}%`, background: first ? "var(--signal)" : "var(--signal-alt)" }} /></span>
            <span className="num text-right" style={{ fontSize: 13, color: first ? "var(--signal)" : undefined }}>{v != null ? `${v} ms` : "–"}</span>
          </li>);
      })}
    </ul>
  );
}
