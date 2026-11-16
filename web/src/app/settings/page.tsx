"use client";
import { EnginesPanel } from "@/components/settings/EnginesPanel";
import { KeyPanel } from "@/components/settings/KeyPanel";
import { VoicesPanel } from "@/components/settings/VoicesPanel";
import { AppShell } from "@/components/shell/AppShell";
import { EffectsPicker } from "@/lib/effects";

export default function Settings() {
  return (
    <AppShell>
      <h1 className="display my-6" style={{ fontSize: "clamp(40px, 7vw, 96px)" }}>Settings</h1>
      <div className="grid gap-6">
        <KeyPanel />
        <section className="glass p-6 space-y-3"><h2 className="display text-2xl">Visual effects</h2>
          <p className="text-sm" style={{ color: "var(--ink-muted)" }}>Auto measures frame rate; Live Call drops to Lite while models generate. Reduced-motion is always respected.</p>
          <EffectsPicker /></section>
        <VoicesPanel />
        <EnginesPanel />
      </div>
    </AppShell>
  );
}
