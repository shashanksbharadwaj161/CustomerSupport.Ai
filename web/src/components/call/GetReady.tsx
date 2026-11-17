"use client";
/** Pre-call checks: microphone, speaker (tap = also unlocks audio on iOS/Safari), WebSocket through the link,
 *  per-language readiness from engine health. Shown before the first call. */
import { useEffect, useRef, useState } from "react";
import { api, wsUrl } from "@/lib/api";
import { humanDuration, LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

export type Ready = {
  languages: Record<Lang, { state: "ready" | "loading" | "unavailable"; stt: string; tts_voice: string | null; tts_engine: string | null;
    robotic: boolean; demo_only: boolean; first_audio_median_ms: number | null; first_audio_n: number }>;
  cuda: boolean; provider: string; real_llm: boolean; active_calls: number; max_calls: number; max_call_seconds: number; busy: boolean;
};
type Check = "idle" | "running" | "ok" | "fail";

export function useReady(pollMs = 4000) {
  const [ready, setReady] = useState<Ready | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => api<Ready>("/api/ready").then((r) => { if (alive) { setReady(r); setOffline(false); } }).catch(() => alive && setOffline(true));
    load();
    const id = window.setInterval(load, pollMs);
    return () => { alive = false; window.clearInterval(id); };
  }, [pollMs]);
  return { ready, offline };
}

function Dot({ s }: { s: Check | "ready" | "loading" | "unavailable" }) {
  const color = s === "ok" || s === "ready" ? "var(--ok)" : s === "fail" || s === "unavailable" ? "var(--danger)" : s === "running" || s === "loading" ? "var(--warn)" : "var(--ink-faint)";
  return <span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 999, background: color }} />;
}

export function GetReady({ ready, onStart, canStart }: { ready: Ready | null; onStart: () => void; canStart: boolean }) {
  const [mic, setMic] = useState<Check>("idle");
  const [micMsg, setMicMsg] = useState("");
  const [level, setLevel] = useState(0);
  const [spk, setSpk] = useState<Check>("idle");
  const [ws, setWs] = useState<Check>("idle");
  const [wsMsg, setWsMsg] = useState("");
  const raf = useRef(0);

  async function testMic() {
    setMic("running"); setMicMsg("Say something…");
    if (!window.isSecureContext) { setMic("fail"); setMicMsg("The page must be opened over https (use the link you were sent)."); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      const an = ctx.createAnalyser(); an.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(new ArrayBuffer(an.fftSize));
      let peak = 0;
      const t0 = performance.now();
      await new Promise<void>((res) => {
        const tick = () => {
          an.getByteTimeDomainData(buf);
          let s = 0; for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; s += v * v; }
          const l = Math.min(1, Math.sqrt(s / buf.length) * 5); peak = Math.max(peak, l); setLevel(l);
          if (performance.now() - t0 < 3000) raf.current = requestAnimationFrame(tick); else res();
        };
        tick();
      });
      stream.getTracks().forEach((t) => t.stop()); ctx.close();
      setLevel(0);
      if (peak > 0.04) { setMic("ok"); setMicMsg("Microphone works."); }
      else { setMic("ok"); setMicMsg("Microphone allowed, but it sounded silent. Check the right mic is selected."); }
    } catch (e: any) {
      setMic("fail");
      setMicMsg(e?.name === "NotAllowedError" ? "Microphone permission was blocked. Allow it in the browser's site settings and try again."
        : e?.name === "NotFoundError" ? "No microphone found." : `Microphone error: ${e?.message || e}`);
    }
  }
  async function testSpeaker() {
    // must run inside a tap: also unlocks audio playback on iOS / Safari
    setSpk("running");
    try {
      const ctx = new AudioContext(); await ctx.resume();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 660; g.gain.value = 0.0001; o.connect(g).connect(ctx.destination); o.start();
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.05); g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.8);
      o.stop(ctx.currentTime + 0.85);
      window.setTimeout(() => { ctx.close(); setSpk("ok"); }, 900);
    } catch { setSpk("fail"); }
  }
  function testWs() {
    setWs("running"); setWsMsg("");
    let done = false;
    const sock = new WebSocket(wsUrl("/api/ws-check"));
    const fail = (m: string) => { if (!done) { done = true; setWs("fail"); setWsMsg(m); try { sock.close(); } catch {} } };
    const timer = window.setTimeout(() => fail("No answer in 6 s: the host PC may be offline or the link has changed."), 6000);
    sock.onopen = () => sock.send("ping");
    sock.onmessage = (e) => { if (e.data === "ping" && !done) { done = true; window.clearTimeout(timer); setWs("ok"); setWsMsg("Live connection works."); sock.close(); } };
    sock.onclose = (e) => { window.clearTimeout(timer); if (!done) fail(e.code === 4401 ? "Passcode expired: reload the page." : e.code === 4403 ? "This address is not allowed." : "Could not open a live connection."); };
  }
  useEffect(() => { testWs(); return () => cancelAnimationFrame(raf.current); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="glass p-5 space-y-4" aria-labelledby="ready-h" data-testid="get-ready">
      <h2 id="ready-h" className="display text-2xl">Get ready</h2>
      <ul className="space-y-3 text-sm">
        <li className="flex flex-wrap items-center gap-3"><Dot s={mic} /><button className="btn" onClick={testMic} disabled={mic === "running"} data-testid="test-mic">Test microphone</button>
          <span aria-live="polite">{micMsg}</span>
          {mic === "running" && <span aria-hidden="true" className="inline-block h-2 w-24 rounded" style={{ background: "var(--line)" }}>
            <span className="block h-2 rounded" style={{ width: `${level * 100}%`, background: "var(--signal)" }} /></span>}</li>
        <li className="flex flex-wrap items-center gap-3"><Dot s={spk} /><button className="btn" onClick={testSpeaker} data-testid="test-speaker">Play test sound</button>
          <span>{spk === "ok" ? "Heard a beep? Then sound works (this tap also enables audio on iPhone)." : "Tap to hear a short beep."}</span></li>
        <li className="flex flex-wrap items-center gap-3"><Dot s={ws} /><button className="btn" onClick={testWs} data-testid="test-ws">Check connection</button>
          <span aria-live="polite" data-testid="ws-status">{ws === "running" ? "Checking…" : wsMsg}</span></li>
      </ul>
      <div>
        <p className="telemetry mb-2">Languages</p>
        <ul className="flex flex-wrap gap-2" data-testid="lang-readiness">
          {LANGS.map((l) => { const s = ready?.languages[l]; return (
            <li key={l} lang={l} className={`lang-badge lang-${l}`} style={{ fontFamily: "var(--font-body)", fontSize: 13 }} data-state={s?.state}>
              <Dot s={s?.state || "loading"} /> {LANG_NAMES[l].native} · {s?.state || "…"}{s?.robotic ? " · robotic voice" : ""}</li>); })}
        </ul>
      </div>
      {ready?.busy && <p role="status" style={{ color: "var(--warn)" }}>The agent is busy with another caller right now ({ready.active_calls}/{ready.max_calls}). Try again in a minute.</p>}
      <button className="btn btn-metal" onClick={onStart} disabled={!canStart || ready?.busy} data-testid="ready-start">Start call</button>
      <p className="text-xs" style={{ color: "var(--ink-muted)" }}>Calls end automatically after {humanDuration(ready?.max_call_seconds || 300)}. Headphones avoid echo.</p>
    </section>
  );
}

export function DemoBanner({ ready }: { ready: Ready | null }) {
  if (!ready) return null;
  const robotic = LANGS.filter((l) => ready.languages[l]?.robotic);
  const delays = LANGS.map((l) => [l, ready.languages[l]?.first_audio_median_ms] as const).filter(([, v]) => v);
  return (
    <div role="note" className="text-sm" data-testid="demo-banner-call" style={{ border: "1px solid color-mix(in srgb, var(--warn) 45%, transparent)",
      background: "color-mix(in srgb, var(--warn) 8%, transparent)", borderRadius: "var(--radius-md)", padding: "10px 14px" }}>
      <strong>Demo.</strong> You are talking to an AI assistant running on {ready.cuda ? "a PC with a GPU" : "an ordinary PC without a GPU (CPU mode)"}.
      {" "}{!ready.real_llm && <>Replies come from a {ready.provider === "fake" ? "scripted test model" : "demo-mode notice (no language model key)"}, not a real assistant. </>}
      Expect a pause before each reply: {delays.length ? delays.map(([l, v]) => `${l.toUpperCase()} about ${(v! / 1000).toFixed(1)} s`).join(", ") + " (measured on this PC)"
        : "several seconds on CPU (not measured on this PC yet)"}.
      {robotic.length > 0 && <> Voices for {robotic.map((l) => LANG_NAMES[l].latin).join(", ")} are <strong>robotic pipeline-testing voices</strong> (MMS, CC-BY-NC, demo only), not natural voices.</>}
      {" "}English, Japanese{ready.languages.hi && !ready.languages.hi.robotic ? " and Hindi" : ""} use Kokoro voices.
    </div>
  );
}
