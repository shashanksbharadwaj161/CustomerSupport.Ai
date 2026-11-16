"use client";
/** Web Audio AnalyserNode -> levels for the Signal (mic level, playback level, 4 bands). */
import type { Levels } from "@/components/signal/Signal";

export class LevelMeter {
  private analyser: AnalyserNode;
  private buf: Uint8Array<ArrayBuffer>;
  private freq: Uint8Array<ArrayBuffer>;
  constructor(ctx: AudioContext, source: AudioNode) {
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 512;
    this.analyser.smoothingTimeConstant = 0.6;
    source.connect(this.analyser);
    this.buf = new Uint8Array(new ArrayBuffer(this.analyser.fftSize));
    this.freq = new Uint8Array(new ArrayBuffer(this.analyser.frequencyBinCount));
  }
  level(): number {
    this.analyser.getByteTimeDomainData(this.buf);
    let s = 0;
    for (let i = 0; i < this.buf.length; i++) { const v = (this.buf[i] - 128) / 128; s += v * v; }
    return Math.min(1, Math.sqrt(s / this.buf.length) * 4);
  }
  bands(): [number, number, number, number] {
    this.analyser.getByteFrequencyData(this.freq);
    const n = this.freq.length, edges = [0, n * 0.04, n * 0.12, n * 0.3, n * 0.6].map(Math.floor);
    const out: number[] = [];
    for (let b = 0; b < 4; b++) {
      let s = 0; const a = edges[b], z = Math.max(edges[b + 1], a + 1);
      for (let i = a; i < z; i++) s += this.freq[i];
      out.push(Math.min(1, s / (z - a) / 200));
    }
    return out as [number, number, number, number];
  }
}

/** Drive a Levels ref from optional mic/out meters every animation frame. Returns stop(). */
export function driveLevels(ref: { current: Levels }, mic?: LevelMeter | null, out?: LevelMeter | null): () => void {
  let raf = 0;
  const tick = () => {
    ref.current.mic = mic ? mic.level() : 0;
    if (out) { ref.current.out = out.level(); ref.current.bands = out.bands(); }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}
