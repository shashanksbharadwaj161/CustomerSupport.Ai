"use client";
import { EnginesPanel } from "@/components/settings/EnginesPanel";
import { KeyPanel } from "@/components/settings/KeyPanel";
import { VoicesPanel } from "@/components/settings/VoicesPanel";
import { AppShell, Module, PageHead } from "@/components/shell/AppShell";
import { AdminGate } from "@/components/shell/AuthGate";
import { EffectsPicker } from "@/lib/effects";

export default function Settings() {
  return (
    <AppShell><AdminGate>
      <PageHead index="05" kicker="Setup" title="Settings"
        sub="Your Anthropic key, the Claude model that answers calls, the spend cap, voices and engines. Everything is stored on this PC." />
      <div className="grid gap-4">
        <KeyPanel />
        <Module index="04" title="Visual effects">
          <p className="muted text-sm mb-4">Auto measures frame rate; Live Call drops to Lite while models generate. Reduced motion is always respected.</p>
          <EffectsPicker />
        </Module>
        <VoicesPanel />
        <EnginesPanel />
      </div>
    </AdminGate></AppShell>
  );
}
