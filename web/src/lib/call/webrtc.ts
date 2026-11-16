"use client";
/** SmallWebRTC client (local default): mic track + data channel; non-trickle ICE (gather, then offer). */
import { api } from "@/lib/api";
import type { CallClient, ServerMsg } from "./types";

export class WebRTCCall implements CallClient {
  kind = "smallwebrtc" as const;
  onMessage: (m: ServerMsg) => void = () => {};
  onClose: (reason: string) => void = () => {};
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private stream: MediaStream | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private ctx: AudioContext | null = null;
  private mic: AudioNode | null = null;
  private out: AudioNode | null = null;
  private ping = 0;

  constructor(private profileId: string | null, private micConstraints: MediaTrackConstraints = { echoCancellation: true, noiseSuppression: true, autoGainControl: true }) {}

  async connect() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: this.micConstraints });
    this.ctx = new AudioContext();
    this.mic = this.ctx.createMediaStreamSource(this.stream);
    const pc = (this.pc = new RTCPeerConnection({ iceServers: [] }));
    pc.addTransceiver(this.stream.getAudioTracks()[0], { direction: "sendrecv" });
    const dc = (this.dc = pc.createDataChannel("app", { ordered: true }));
    dc.onopen = () => {
      this.send({ type: "ready" });
      this.ping = window.setInterval(() => { if (dc.readyState === "open") dc.send("ping: " + Date.now()); }, 1000);
    };
    dc.onmessage = (e) => {
      try { const m = JSON.parse(e.data); if (m && m.type === "shaon") this.onMessage(m); } catch {}
    };
    pc.ontrack = (e) => {
      const remote = e.streams[0] || new MediaStream([e.track]);
      // Chrome only feeds remote WebRTC audio into WebAudio when it is also attached to a media element
      this.audioEl = new Audio(); this.audioEl.autoplay = true; this.audioEl.srcObject = remote;
      this.audioEl.play().catch(() => {});
      if (this.ctx) this.out = this.ctx.createMediaStreamSource(remote);
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed" || pc.connectionState === "closed") this.onClose(pc.connectionState);
    };
    await pc.setLocalDescription(await pc.createOffer());
    await new Promise<void>((res) => {
      if (pc.iceGatheringState === "complete") return res();
      const t = window.setTimeout(res, 2500);
      pc.addEventListener("icegatheringstatechange", () => { if (pc.iceGatheringState === "complete") { window.clearTimeout(t); res(); } });
    });
    const ans = await api<{ sdp: string; type: RTCSdpType; pc_id: string }>("/api/calls/offer", {
      method: "POST", json: { sdp: pc.localDescription!.sdp, type: pc.localDescription!.type, requestData: { profile_id: this.profileId } },
    });
    await pc.setRemoteDescription({ sdp: ans.sdp, type: ans.type });
  }

  send(msg: Record<string, unknown>) {
    if (this.dc?.readyState === "open") this.dc.send(JSON.stringify(msg));
  }
  micNode() { return this.ctx && this.mic ? { ctx: this.ctx, node: this.mic } : null; }
  outNode() { return this.ctx && this.out ? { ctx: this.ctx, node: this.out } : null; }

  disconnect() {
    window.clearInterval(this.ping);
    try { this.dc?.close(); } catch {}
    try { this.pc?.close(); } catch {}
    this.stream?.getTracks().forEach((t) => t.stop());
    if (this.audioEl) { this.audioEl.srcObject = null; }
    this.ctx?.close().catch(() => {});
    this.onClose("ended");
  }
}
