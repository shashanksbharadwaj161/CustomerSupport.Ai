"use client";
/** Five scripts: native text is DOM text (Noto); the mono Latin name is the ASCII-layer name. Hover = language hue. */
const LANGS = [
  { k: "en", n: "English", latin: "ENGLISH", s: "Latin", line: "Hello, how can I help you today?", v: "Kokoro · Whisper" },
  { k: "ja", n: "日本語", latin: "NIHONGO", s: "Kana / Kanji", line: "本日はどのようなご用件でしょうか。", v: "Kokoro · Whisper" },
  { k: "hi", n: "हिन्दी", latin: "HINDI", s: "Devanagari", line: "नमस्ते, मैं आपकी क्या मदद कर सकती हूँ?", v: "Kokoro · MMS" },
  { k: "bn", n: "বাংলা", latin: "BANGLA", s: "Bengali", line: "নমস্কার, আমি আপনাকে কীভাবে সাহায্য করতে পারি?", v: "MMS (demo voice)" },
  { k: "kn", n: "ಕನ್ನಡ", latin: "KANNADA", s: "Kannada", line: "ನಮಸ್ಕಾರ, ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?", v: "MMS (demo voice)" },
];

export function Languages() {
  return (
    <section aria-labelledby="langs-h" className="mx-auto py-16 md:py-24" style={{ maxWidth: "var(--content-max)", padding: "0 var(--gutter)" }}>
      <p className="kicker"><span className="faint">02 </span>Five scripts, one agent</p>
      <h2 id="langs-h" className="display mt-3 mb-10" style={{ fontSize: "clamp(32px, 5vw, 72px)" }}>Switch language any turn</h2>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 stagger">
        {LANGS.map((l, i) => (
          <li key={l.k} className={`hud lang-card lang-${l.k}`} style={{ ["--tick-c" as string]: `var(--lang-${l.k})` }}>
            <div className="flex items-center justify-between px-4 pt-4">
              <span className="num faint" style={{ fontSize: 10 }}>L{String(i + 1).padStart(2, "0")}</span>
              <span className="mono" style={{ fontSize: 10, letterSpacing: "0.12em" }} aria-hidden="true">{l.latin}</span>
            </div>
            <p lang={l.k} className="px-4 mt-6" style={{ fontSize: 34, lineHeight: 1.3 }}>{l.n}</p>
            <p lang={l.k} className="px-4 mt-3" style={{ color: "var(--ink)", fontSize: 15 }}>{l.line}</p>
            <div className="flex items-center justify-between gap-2 px-4 py-3 mt-6" style={{ borderTop: "1px solid var(--line)" }}>
              <span className="telemetry" style={{ fontSize: 10 }}>{l.s}</span>
              <span className="telemetry" style={{ fontSize: 10 }}>{l.v}</span>
            </div>
          </li>))}
      </ul>
    </section>
  );
}
