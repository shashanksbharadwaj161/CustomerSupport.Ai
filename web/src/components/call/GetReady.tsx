"use client";
/** Pre-call checks: microphone, speaker (tap = also unlocks audio on iOS/Safari), WebSocket through the link,
 *  per-language readiness from engine health. Shown before the first call. */
import { useEffect, useRef, useState } from "react";
import { api, wsUrl } from "@/lib/api";
import { humanDuration, LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

export type Ready = {
  languages: Record<Lang, { state: "ready" | "loading" | "missing" | "unavailable"; stt: string; tts_voice: string | null; tts_engine: string | null;
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

function Dot({ s }: { s: Check | "ready" | "loading" | "missing" | "unavailable" }) {
  const c = s === "ok" || s === "ready" ? "light-ok" : s === "fail" || s === "unavailable" || s === "missing" ? "light-danger" : s === "running" || s === "loading" ? "light-warn" : "";
  return <span aria-hidden="true" className={`light ${c}`} />;
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

  const row = "grid grid-cols-[14px_auto_1fr] items-center gap-3 py-2";
  return (
    <section className="module" aria-labelledby="ready-h" data-testid="get-ready">
      <div className="module-head"><span className={`light ${mic === "ok" && ws === "ok" ? "light-ok" : "light-warn"}`} /><span className="idx">R</span>
        <h2 id="ready-h" className="ttl" style={{ font: "inherit", margin: 0 }}>Get ready</h2><span className="spacer" /><span>3 checks</span></div>
      <div className="module-body grid gap-4">
        <ul className="text-sm" style={{ borderTop: "1px solid var(--line)" }}>
          <li className={row} style={{ borderBottom: "1px solid var(--line)" }}><Dot s={mic} /><button className="btn btn-sm" onClick={testMic} disabled={mic === "running"} data-testid="test-mic">Test microphone</button>
            <span aria-live="polite" className="muted">{micMsg || "Say a few words after you press it."}
              {mic === "running" && <span aria-hidden="true" className="meter mt-2" style={{ display: "block", width: 140 }}><span style={{ width: `${level * 100}%` }} /></span>}</span></li>
          <li className={row} style={{ borderBottom: "1px solid var(--line)" }}><Dot s={spk} /><button className="btn btn-sm" onClick={testSpeaker} data-testid="test-speaker">Play test sound</button>
            <span className="muted">{spk === "ok" ? "Heard a beep? Sound works (this tap also enables audio on iPhone)." : "Tap to hear a short beep."}</span></li>
          <li className={row} style={{ borderBottom: "1px solid var(--line)" }}><Dot s={ws} /><button className="btn btn-sm" onClick={testWs} data-testid="test-ws">Check connection</button>
            <span aria-live="polite" data-testid="ws-status" className="muted">{ws === "running" ? "Checking…" : wsMsg}</span></li>
        </ul>
        <div>
          <p className="label mb-2">Languages on this PC</p>
          <ul className="flex flex-wrap gap-2" data-testid="lang-readiness">
            {LANGS.map((l) => { const s = ready?.languages[l]; return (
              <li key={l} lang={l} className={`lang-badge lang-${l}`} style={{ fontFamily: "var(--font-body)", fontSize: 13, padding: "4px 10px" }} data-state={s?.state}>
                <Dot s={s?.state || "loading"} /> {LANG_NAMES[l].native} <span className="faint" style={{ fontSize: 11 }} lang="en">{s?.state === "missing" ? "not downloaded" : s?.state || "…"}{s?.robotic ? " · robotic" : ""}</span></li>); })}
          </ul>
        </div>
        {ready?.busy && <p role="status" className="notice notice-warn">The agent is busy with another caller right now ({ready.active_calls}/{ready.max_calls}). Try again in a minute.</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn btn-primary" onClick={onStart} disabled={!canStart || ready?.busy} data-testid="ready-start">Start call <span className="arrow">→</span></button>
          <span className="hint">Calls end automatically after {humanDuration(ready?.max_call_seconds || 300)}. Headphones avoid echo.</span>
        </div>
      </div>
    </section>
  );
}

export function DemoBanner({ ready }: { ready: Ready | null }) {
  if (!ready) return null;
  const robotic = LANGS.filter((l) => ready.languages[l]?.robotic);
  const delays = LANGS.map((l) => [l, ready.languages[l]?.first_audio_median_ms] as const).filter(([, v]) => v);
  const delayText = delays.length ? delays.map(([l, v]) => `${l.toUpperCase()} ~${(v! / 1000).toFixed(1)} s`).join(", ") : "several seconds";
  return (
    <details role="note" className="notice notice-warn" data-testid="demo-banner-call" style={{ display: "block", color: "var(--ink)" }}>
      <summary style={{ cursor: "pointer" }}>
        <strong style={{ color: "var(--warn)" }}>Demo</strong> · {ready.cuda ? "GPU" : "CPU"} · {ready.real_llm ? "Claude replies" : ready.provider === "fake" ? "scripted test replies" : "no key: demo notice"} · first audio {delayText}
        {robotic.length > 0 && <> · robotic {robotic.map((l) => l.toUpperCase()).join("/")} voices</>}
        <span className="faint"> (details)</span>
      </summary>
      <p className="mt-2">You are talking to an AI assistant running on {ready.cuda ? "a PC with a GPU" : "an ordinary PC without a GPU (CPU mode)"}.
      {" "}{!ready.real_llm && <>Replies come from a {ready.provider === "fake" ? "scripted test model" : "demo-mode notice (no language model key)"}, not a real assistant. </>}
      Expect a pause before each reply: {delays.length ? delays.map(([l, v]) => `${l.toUpperCase()} about ${(v! / 1000).toFixed(1)} s`).join(", ") + " (measured on this PC)"
        : "several seconds on CPU (not measured on this PC yet)"}.
      {robotic.length > 0 && <> Voices for {robotic.map((l) => LANG_NAMES[l].latin).join(", ")} are <strong>robotic pipeline-testing voices</strong> (MMS, CC-BY-NC, demo only), not natural voices.</>}
      {" "}English, Japanese{ready.languages.hi && !ready.languages.hi.robotic ? " and Hindi" : ""} use Kokoro voices.</p>
    </details>
  );
}
