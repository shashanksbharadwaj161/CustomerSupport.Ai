"use client";
/** WebSocket client (tunnel transport): raw PCM16 over binary frames, JSON over text frames. */
import { wsUrl } from "@/lib/api";
import type { CallClient, ServerMsg } from "./types";

export class WebSocketCall implements CallClient {
  kind = "websocket" as const;
  onMessage: (m: ServerMsg) => void = () => {};
  onClose: (reason: string) => void = () => {};
  private ws: WebSocket | null = null;
  private stream: MediaStream | null = null;
  private inCtx: AudioContext | null = null;
  private outCtx: AudioContext | null = null;
  private mic: AudioNode | null = null;
  private player: AudioWorkletNode | null = null;
  private outRate = 24000;
  private closed = false;

  constructor(private profileId: string | null, private micConstraints: MediaTrackConstraints = { echoCancellation: true, noiseSuppression: true, autoGainControl: true }) {}

  async connect() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: this.micConstraints });
    this.inCtx = new AudioContext({ sampleRate: 16000 });
    this.outCtx = new AudioContext({ sampleRate: this.outRate });
    await this.inCtx.audioWorklet.addModule("/worklets/pcm-capture.js");
    await this.outCtx.audioWorklet.addModule("/worklets/pcm-player.js");
    this.mic = this.inCtx.createMediaStreamSource(this.stream);
    const cap = new AudioWorkletNode(this.inCtx, "pcm-capture");
    this.mic.connect(cap);
    this.player = new AudioWorkletNode(this.outCtx, "pcm-player");
    this.player.connect(this.outCtx.destination);
    await this.outCtx.resume();

    const q = new URLSearchParams();
    if (this.profileId) q.set("profile_id", this.profileId);
    const ws = (this.ws = new WebSocket(wsUrl(`/api/calls/ws?${q}`)));
    ws.binaryType = "arraybuffer";
    cap.port.onmessage = (e) => { if (ws.readyState === WebSocket.OPEN) ws.send(e.data); };
    await new Promise<void>((res, rej) => {
      ws.onopen = () => res();
      ws.onerror = () => rej(new Error("WebSocket failed to connect"));
    });
    ws.onmessage = (e) => {
      if (typeof e.data === "string") {
        try {
          const m = JSON.parse(e.data);
          if (m?.type !== "shaon") return;
          if (m.event === "interrupted") this.player?.port.postMessage("flush");
          this.onMessage(m);
        } catch {}
        return;
      }
      const i16 = new Int16Array(e.data as ArrayBuffer);
      const f32 = new Float32Array(i16.length);
      for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
      this.player?.port.postMessage(f32.buffer, [f32.buffer]);
    };
    ws.onclose = (e) => { if (!this.closed) this.onClose(`closed (${e.code})`); };
    this.send({ type: "ready" });
  }

  send(msg: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }
  micNode() { return this.inCtx && this.mic ? { ctx: this.inCtx, node: this.mic } : null; }
  outNode() { return this.outCtx && this.player ? { ctx: this.outCtx, node: this.player } : null; }

  disconnect() {
    this.closed = true;
    try { this.ws?.close(); } catch {}
    this.stream?.getTracks().forEach((t) => t.stop());
    this.inCtx?.close().catch(() => {});
    this.outCtx?.close().catch(() => {});
    this.onClose("ended");
  }
}
