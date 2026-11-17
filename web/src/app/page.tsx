import Link from "next/link";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Languages } from "@/components/landing/Languages";
import { PresetGallery } from "@/components/landing/PresetGallery";
import { SetupStatus } from "@/components/landing/SetupStatus";
import { AppShell } from "@/components/shell/AppShell";

export default function Landing() {
  return (
    <AppShell bare>
      <Hero />
      <HowItWorks />
      <Languages />
      <PresetGallery />
      <SetupStatus />
      <section className="mx-auto text-center" style={{ maxWidth: "var(--content-max)", padding: "64px var(--gutter)" }}>
        <p className="kicker">Ready</p>
        <h2 className="display mt-4 mb-8" style={{ fontSize: "clamp(40px, 8vw, 128px)" }}>Talk to it.</h2>
        <Link href="/call/" className="btn btn-metal btn-lg">Start a live call <span className="arrow">→</span></Link>
      </section>
      <footer className="mx-auto text-xs space-y-2" style={{ maxWidth: "var(--content-max)", padding: "24px var(--gutter)", color: "var(--ink-muted)", borderTop: "1px solid var(--line)" }}>
        <p>ShaOn Voice AI demo. Every agent says it is an AI assistant. Demo businesses and data are fictional.</p>
        <p><span className="badge-demo">demo only</span> MMS and OmniVoice weights are CC-BY-NC: private demos only, never commercial.</p>
      </footer>
    </AppShell>
  );
}
