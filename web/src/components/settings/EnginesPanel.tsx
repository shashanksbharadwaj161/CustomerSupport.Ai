"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type E = { kind: string; license: string; demo_only: boolean; installed: boolean; weights_cached: boolean; loaded: boolean;
  verified_here: string | null; pending: string | null; load_error: string | null };

export function EnginesPanel() {
  const [d, setD] = useState<{ cuda: boolean; engines: Record<string, E> } | null>(null);
  useEffect(() => { api("/api/engines").then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <section className="glass p-6 space-y-3" aria-labelledby="eng-h">
      <h2 id="eng-h" className="display text-2xl">Speech engines</h2>
      <p className="text-sm" style={{ color: "var(--ink-muted)" }}>{d.cuda ? "CUDA GPU detected: GPU engine profile." : "No CUDA GPU: CPU profile (Whisper small, Kokoro)."} Status is shown as measured, never assumed.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="engines-table">
          <thead><tr className="telemetry text-left"><th className="py-1 pr-3">Engine</th><th className="pr-3">Kind</th><th className="pr-3">Installed</th><th className="pr-3">Weights</th><th className="pr-3">Status</th><th>License</th></tr></thead>
          <tbody>{Object.entries(d.engines).map(([n, e]) => (
            <tr key={n} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="py-2 pr-3 mono">{n}</td><td className="pr-3">{e.kind}</td>
              <td className="pr-3">{e.installed ? "yes" : "no"}</td><td className="pr-3">{e.weights_cached ? "cached" : "not downloaded"}</td>
              <td className="pr-3">{e.verified_here ? <span style={{ color: "var(--ok)" }}>verified: {e.verified_here}</span> : <span style={{ color: "var(--warn)" }}>PENDING</span>}
                {e.load_error && <div style={{ color: "var(--danger)" }}>{e.load_error}</div>}</td>
              <td>{e.license}{e.demo_only && <span className="badge-demo ml-2">demo only</span>}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </section>
  );
}
