// Playback for the WebSocket transport: a ring buffer of Float32 samples at the context rate (24 kHz).
class PcmPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.q = []; this.cur = null; this.pos = 0; this.playing = false;
    this.port.onmessage = (e) => {
      if (e.data === "flush") { this.q = []; this.cur = null; this.pos = 0; return; }
      this.q.push(new Float32Array(e.data));
    };
  }
  process(_inputs, outputs) {
    const out = outputs[0][0];
    let i = 0;
    while (i < out.length) {
      if (!this.cur || this.pos >= this.cur.length) {
        this.cur = this.q.shift() || null; this.pos = 0;
        if (!this.cur) break;
      }
      const n = Math.min(out.length - i, this.cur.length - this.pos);
      out.set(this.cur.subarray(this.pos, this.pos + n), i);
      i += n; this.pos += n;
    }
    for (; i < out.length; i++) out[i] = 0;
    const active = !!this.cur || this.q.length > 0;
    if (active !== this.playing) { this.playing = active; this.port.postMessage({ playing: active }); }
    return true;
  }
}
registerProcessor("pcm-player", PcmPlayer);
