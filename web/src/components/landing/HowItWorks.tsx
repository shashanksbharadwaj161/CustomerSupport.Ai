"use client";
/** "How a turn flows": an interactive signal chain. Click / arrow keys select a stage; a packet runs the chain. */
import { useState } from "react";

const STAGES = [
  { k: "MIC", t: "Listens", d: "Your browser streams microphone audio to this PC over WebRTC (or a WebSocket through the share tunnel). Nothing goes to a cloud speech service.", m: "WebRTC · 16 kHz" },
  { k: "VAD", t: "Finds the turn", d: "Silero voice-activity detection cuts speech into turns locally, so the agent answers when you stop talking.", m: "Silero VAD" },
  { k: "LID", t: "Identifies the language", d: "Whisper language ID over five candidates. When it is unsure, the script of the transcript decides; a manual override always wins.", m: "Whisper small · script check" },
  { k: "STT", t: "Transcribes", d: "Per-language speech-to-text: Whisper for English and Japanese, MMS for Hindi, Bengali and Kannada on CPU (IndicConformer with a token).", m: "Whisper · MMS" },
  { k: "LLM", t: "Answers from your site", d: "Claude, the model you pick in Settings, answers only from your crawled website, retrieved passages and allowed tools, in native script.", m: "Claude · RAG · tools" },
  { k: "GRD", t: "Checks the reply", d: "Local guardrail rules plus one combined model check; anything unsafe or unsupported becomes a polite hand-off to a human.", m: "3-layer guardrails" },
  { k: "TTS", t: "Speaks back", d: "The reply's script picks the voice; sentences are spoken as soon as they are ready. Kokoro for en/ja/hi, MMS (demo-only) for bn/kn.", m: "Kokoro · MMS" },
];

export function HowItWorks() {
  const [i, setI] = useState(4);
  const s = STAGES[i];
  return (
    <section aria-labelledby="how-h" className="mx-auto py-16 md:py-24" style={{ maxWidth: "var(--content-max)", padding: "0 var(--gutter)" }}>
      <p className="kicker"><span className="faint">01 </span>Signal chain</p>
      <h2 id="how-h" className="display mt-3 mb-10" style={{ fontSize: "clamp(32px, 5vw, 72px)" }}>How one turn flows</h2>
      <div className="module">
        <div className="module-head"><span className="light light-live" /><span className="ttl">Pipeline · 7 stages</span><span className="spacer" />
          <span>select a stage</span></div>
        <div className="module-body">
          <ol className="chain" role="tablist" aria-label="Pipeline stages"
            onKeyDown={(e) => { if (e.key === "ArrowRight") setI((x) => Math.min(STAGES.length - 1, x + 1)); if (e.key === "ArrowLeft") setI((x) => Math.max(0, x - 1)); }}>
            {STAGES.map((st, j) => (
              <li key={st.k} role="presentation">
                <button type="button" role="tab" aria-selected={i === j} tabIndex={i === j ? 0 : -1} onClick={() => setI(j)} className="chain-node"
                  id={`stage-${st.k}`} aria-controls="stage-detail">
                  <span className="num faint" style={{ fontSize: 10 }}>{String(j + 1).padStart(2, "0")}</span>
                  <span className="mono" style={{ fontSize: 15, fontWeight: 600 }}>{st.k}</span>
                  <span style={{ fontSize: 12 }} className="muted">{st.t}</span>
                </button>
              </li>))}
          </ol>
          <div id="stage-detail" role="tabpanel" aria-labelledby={`stage-${s.k}`} className="grid md:grid-cols-[auto_1fr] gap-6 mt-6 pt-6 items-start" style={{ borderTop: "1px solid var(--line)" }}>
            <p aria-hidden="true" className="display" style={{ fontSize: "clamp(64px, 9vw, 128px)", color: "transparent", WebkitTextStroke: "1px var(--signal)", lineHeight: 0.85 }}>{s.k}</p>
            <div>
              <p className="telemetry" style={{ color: "var(--signal)" }}>{s.m}</p>
              <h3 className="headline mt-2" style={{ fontSize: 28 }}>{s.t}</h3>
              <p className="muted mt-3 max-w-[60ch]" style={{ lineHeight: 1.6 }}>{s.d}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
