"use client";
/** Honest demo-mode banner: shows what is missing (key, models) as reported by /api/health. */
import { useEffect, useState } from "react";

type Health = { mode: "full" | "demo"; reasons: string[] };

export function StatusBanner() {
  const [h, setH] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => fetch("/api/health").then((r) => r.json()).then((j) => { if (alive) { setH(j); setOffline(false); } })
      .catch(() => alive && setOffline(true));
    load();
    const id = window.setInterval(load, 15000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  if (offline) return <Banner tone="danger" text="API offline: start the backend with scripts/start.sh" />;
  if (!h || h.mode === "full") return null;
  return <Banner tone="warn" text={`Demo mode: ${h.reasons.join(" · ")}`} />;
}

function Banner({ tone, text }: { tone: "warn" | "danger"; text: string }) {
  return (
    <div role="status" data-testid="demo-banner" className="mx-auto w-full text-sm" style={{ maxWidth: "var(--content-max)", padding: "0 var(--gutter)" }}>
      <div style={{ border: `1px solid color-mix(in srgb, var(--${tone}) 45%, transparent)`, color: `var(--${tone})`,
        background: `color-mix(in srgb, var(--${tone}) 10%, transparent)`, borderRadius: "var(--radius-md)", padding: "8px 14px", margin: "4px 0 16px" }}>
        {text}
      </div>
    </div>
  );
}
