"use client";
/** Live readiness of THIS install (no fakes): key, model, spend, per-language engines. Links to Settings. */
import Link from "next/link";
import { useEffect, useState } from "react";
import { useHealth } from "@/components/shell/AppShell";
import { useAuth } from "@/components/shell/AuthGate";
import { LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

type Ready = { languages: Record<Lang, { state: string; stt: string; tts_voice: string | null; robotic: boolean }> };
const LIGHT: Record<string, string> = { ready: "light-ok", loading: "light-warn", missing: "light-danger", unavailable: "light-danger" };

export function SetupStatus() {
  const { h } = useHealth(10000);
  const [r, setR] = useState<Ready | null>(null);
  const ctx = useAuth();
  const visitor = !!ctx && ctx.auth.visitorMode && ctx.auth.role !== "admin";
  useEffect(() => {
    let alive = true;
    const load = () => fetch("/api/ready").then((x) => (x.ok ? x.json() : null)).then((j) => alive && j && setR(j)).catch(() => {});
    load();
    const id = window.setInterval(load, 8000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  const real = h?.provider === "anthropic";
  return (
    <section aria-labelledby="setup-h" className="mx-auto py-16 md:py-24" style={{ maxWidth: "var(--content-max)", padding: "0 var(--gutter)" }}>
      <p className="kicker"><span className="faint">04 </span>This install, live</p>
      <h2 id="setup-h" className="display mt-3 mb-10" style={{ fontSize: "clamp(32px, 5vw, 72px)" }}>Ready check</h2>
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        {!visitor && (
          <div className="module">
            <div className="module-head"><span className={`light ${real ? "light-ok" : "light-warn"}`} /><span className="ttl">Language model</span></div>
            <div className="module-body">
              <dl className="rows">
                <dt>Key</dt><dd>{!h ? "…" : h.provider === "anthropic" ? "configured (encrypted)" : h.provider === "fake" ? "test mode (fake model)" : "not set: replies are a fixed demo notice"}</dd>
                <dt>Model</dt><dd className="mono">{real ? h?.model : "—"}</dd>
                <dt>Spend</dt><dd className="num">{h?.spend ? `$${h.spend.spent_usd.toFixed(2)} of $${h.spend.cap_usd.toFixed(2)}` : "—"}</dd>
              </dl>
              <Link href="/settings/" className="btn btn-primary mt-5">{real ? "Change model or cap" : "Add your API key"} <span className="arrow">→</span></Link>
            </div>
          </div>
        )}
        <div className="module">
          <div className="module-head"><span className="light light-live" /><span className="ttl">Speech engines per language</span></div>
          <div className="module-body">
            {!r ? <div className="grid gap-2">{LANGS.map((l) => <div key={l} className="skeleton" style={{ height: 34 }} />)}</div> : (
              <ul className="grid gap-2">
                {LANGS.map((l) => {
                  const s = r.languages[l];
                  return (
                    <li key={l} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2" style={{ borderBottom: "1px solid var(--line)" }}>
                      <span className={`light ${LIGHT[s.state] || ""}`} />
                      <span lang={l} className={`lang-${l}`} style={{ minWidth: 84 }}>{LANG_NAMES[l].native}</span>
                      <span className="mono muted" style={{ fontSize: 12 }}>{s.stt} → {s.tts_voice || "no voice"}</span>
                      <span className="flex-1" />
                      <span className={`chip ${s.state === "ready" ? "chip-ok" : s.state === "loading" ? "chip-warn" : "chip-danger"}`}>
                        {s.state === "missing" ? "not downloaded" : s.state}</span>
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="hint mt-3">&quot;not downloaded&quot;: run ShaOn-Install.bat to fetch that language&apos;s models. Bengali and Kannada voices are robotic test voices (MMS, non-commercial, demo only).</p>
          </div>
        </div>
      </div>
    </section>
  );
}
