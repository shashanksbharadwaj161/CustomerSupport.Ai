import Link from "next/link";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Hero } from "@/components/landing/Hero";
import { PresetGallery } from "@/components/landing/PresetGallery";
import { CapsuleNav } from "@/components/shell/CapsuleNav";

const LANGS = [
  { k: "en", n: "English", s: "Latin", line: "Hello, how can I help you today?" },
  { k: "ja", n: "日本語", s: "Kana / Kanji", line: "本日はどのようなご用件でしょうか。" },
  { k: "hi", n: "हिन्दी", s: "Devanagari", line: "नमस्ते, मैं आपकी क्या मदद कर सकती हूँ?" },
  { k: "bn", n: "বাংলা", s: "Bengali", line: "নমস্কার, আমি আপনাকে কীভাবে সাহায্য করতে পারি?" },
  { k: "kn", n: "ಕನ್ನಡ", s: "Kannada", line: "ನಮಸ್ಕಾರ, ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?" },
];

export default function Landing() {
  return (
    <>
      <header className="fixed top-0 inset-x-0 z-40 flex justify-center" style={{ padding: "12px var(--gutter)" }}>
        <CapsuleNav />
      </header>
      <main id="main">
        <Hero />
        <HowItWorks />
        <section aria-labelledby="langs-h" className="py-24 px-[var(--gutter)] max-w-[var(--content-max)] mx-auto">
          <h2 id="langs-h" className="display mb-10" style={{ fontSize: "clamp(36px, 6vw, 88px)" }}>Switch language any turn</h2>
          <ul className="grid gap-4 md:grid-cols-5">{LANGS.map((l) => (
            <li key={l.k} className="glass p-5" lang={l.k}>
              <p className={`lang-badge lang-${l.k}`} lang="en">{l.k.toUpperCase()} · {l.s}</p>
              <p className="text-3xl my-4" style={{ color: `var(--lang-${l.k})` }}>{l.n}</p>
              <p className="text-sm" style={{ color: "var(--ink-muted)" }}>{l.line}</p>
            </li>))}</ul>
        </section>
        <PresetGallery />
        <section className="py-24 px-[var(--gutter)] text-center">
          <h2 className="display mb-8" style={{ fontSize: "clamp(36px, 7vw, 110px)" }}>Talk to it.</h2>
          <Link href="/call/" className="btn btn-metal" style={{ padding: "16px 34px", fontSize: 18 }}>Start a demo</Link>
        </section>
      </main>
      <footer className="px-[var(--gutter)] py-10 text-xs space-y-2" style={{ color: "var(--ink-muted)", borderTop: "1px solid var(--line)" }}>
        <p>ShaOn Voice AI demo. Every agent says it is an AI assistant. Demo businesses and data are fictional.</p>
        <p><span className="badge-demo">demo only</span> OmniVoice voices use CC-BY-NC weights: private demos only, never commercial.</p>
      </footer>
    </>
  );
}
