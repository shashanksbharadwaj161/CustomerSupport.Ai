"use client";
/**
 * D0 Signal lab: drive every Signal state with real Web Audio levels (mic, or a synthetic
 * "agent voice" through an AnalyserNode). Used for the performance check while models run.
 */
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { emptyLevels, type Levels, type SignalState } from "@/components/signal/Signal";
import { driveLevels, LevelMeter } from "@/lib/audio";
import { EffectsPicker, useEffectsTier } from "@/lib/effects";
import { LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

const Signal = dynamic(() => import("@/components/signal/Signal").then((m) => m.Signal), { ssr: false });
const STATES: SignalState[] = ["idle", "listening", "thinking", "speaking", "switch", "handoff", "error"];

export default function Lab() {
  const [state, setState] = useState<SignalState>("idle");
  const [lang, setLang] = useState<Lang>("en");
  const [mic, setMic] = useState(false);
  const [synth, setSynth] = useState(false);
  const [fps, setFps] = useState(0);
  const levels = useRef<Levels>(emptyLevels());
  const { tier } = useEffectsTier();

  useEffect(() => { // measured frame rate of the page (shown + read by Playwright)
    let n = 0, raf = 0, last = performance.now();
    const tick = (t: number) => { n++; if (t - last >= 1000) { setFps(n); n = 0; last = t; } raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    if (!mic && !synth) return;
    const ctx = new AudioContext();
    let stream: MediaStream | null = null, stop = () => {};
    let osc: OscillatorNode | null = null, lfo: OscillatorNode | null = null;
    (async () => {
      let micMeter: LevelMeter | null = null, outMeter: LevelMeter | null = null;
      if (mic) {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        micMeter = new LevelMeter(ctx, ctx.createMediaStreamSource(stream));
      }
      if (synth) { // synthetic voice-like signal: carrier with syllable-rate amplitude modulation
        osc = ctx.createOscillator(); osc.type = "sawtooth"; osc.frequency.value = 180;
        lfo = ctx.createOscillator(); lfo.frequency.value = 4.5;
        const amp = ctx.createGain(); amp.gain.value = 0.5;
        const lfoGain = ctx.createGain(); lfoGain.gain.value = 0.5;
        lfo.connect(lfoGain).connect(amp.gain); osc.connect(amp);
        osc.start(); lfo.start();
        outMeter = new LevelMeter(ctx, amp);
      }
      stop = driveLevels(levels, micMeter, outMeter);
    })();
    return () => { stop(); osc?.stop(); lfo?.stop(); stream?.getTracks().forEach((t) => t.stop()); ctx.close(); levels.current = emptyLevels(); };
  }, [mic, synth]);

  return (
    <AppShell wide>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Signal state={state} lang={lang} levelsRef={levels} className="h-[70vh] min-h-[360px] w-full" />
        <aside className="glass p-5 space-y-5" aria-label="Signal controls">
          <h1 className="display text-3xl">Signal lab</h1>
          <p className="telemetry" data-testid="fps">{fps} fps · tier {tier}</p>
          <EffectsPicker />
          <fieldset><legend className="telemetry mb-2">State</legend>
            <div className="flex flex-wrap gap-2">{STATES.map((s) => (
              <button key={s} className="btn" aria-pressed={s === state} onClick={() => setState(s)}
                style={{ borderColor: s === state ? "var(--signal)" : undefined }}>{s}</button>))}</div>
          </fieldset>
          <fieldset><legend className="telemetry mb-2">Language</legend>
            <div className="flex flex-wrap gap-2">{LANGS.map((l) => (
              <button key={l} lang={l} className={`btn lang-${l}`} aria-pressed={l === lang} onClick={() => { setState("switch"); setLang(l); }}>
                {LANG_NAMES[l].native}</button>))}</div>
          </fieldset>
          <fieldset><legend className="telemetry mb-2">Audio input</legend>
            <div className="flex flex-wrap gap-2">
              <button className="btn" aria-pressed={mic} onClick={() => setMic((m) => !m)}>{mic ? "Mic on" : "Use mic"}</button>
              <button className="btn" aria-pressed={synth} onClick={() => setSynth((s) => !s)}>{synth ? "Synthetic voice on" : "Synthetic voice"}</button>
            </div>
          </fieldset>
        </aside>
      </div>
    </AppShell>
  );
}
