"use client";
/** Spatial preset gallery (basement / DNA-carousel ideas, re-implemented): 3D ring, keys, drag, buttons. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api } from "@/lib/api";

const PRESETS = [
  { k: "bank_support", t: "Bank support", d: "Balances, lost cards, branch hours, deposit rates. Fake data, AI disclosure, never reads full numbers.", tools: "balance lookup · card block" },
  { k: "tourism", t: "Tourism desk", d: "Heritage tours, river cruises, Japan trips and visa help from the operator's own site.", tools: "itinerary search" },
  { k: "ecommerce", t: "Store help", d: "Order status, delivery and returns in five languages.", tools: "order lookup" },
  { k: "clinic_frontdesk", t: "Clinic front desk", d: "Appointments and hours. Never gives medical advice; emergencies escalate.", tools: "appointment slots" },
  { k: "custom", t: "Custom agent", d: "Describe any role in your own words and point it at your website.", tools: "no tools" },
];

export function PresetGallery() {
  const [i, setI] = useState(0);
  const [busy, setBusy] = useState(false);
  const drag = useRef<number | null>(null);
  const router = useRouter();
  const n = PRESETS.length, step = 360 / n;
  const go = (d: number) => setI((x) => (x + d + n) % n);
  async function use(k: string) {
    setBusy(true);
    try { const p: any = await api("/api/profiles", { method: "POST", json: { preset: k } }); router.push(`/studio/?id=${p.id}`); }
    catch { router.push("/studio/"); }
  }
  return (
    <section aria-labelledby="gallery-h" aria-roledescription="carousel" className="py-16 md:py-24 px-[var(--gutter)] overflow-hidden"
      onKeyDown={(e) => { if (e.key === "ArrowRight") go(1); if (e.key === "ArrowLeft") go(-1); }}>
      <div className="max-w-[var(--content-max)] mx-auto">
        <p className="kicker"><span className="faint">03 </span>Agent presets</p>
        <h2 id="gallery-h" className="display mt-3 mb-3" style={{ fontSize: "clamp(32px, 5vw, 72px)" }}>Start from a preset</h2>
        <p className="mb-10" style={{ color: "var(--ink-muted)" }}>Every preset ships with persona, guardrails, disclaimers and tools. Change anything in the Studio.</p>
        <div className="relative h-[380px] select-none" style={{ perspective: "1400px" }}
          onPointerDown={(e) => { drag.current = e.clientX; }} onPointerUp={(e) => { if (drag.current !== null) { const dx = e.clientX - drag.current; if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1); drag.current = null; } }}>
          <div className="absolute inset-0" style={{ transformStyle: "preserve-3d", transform: `translateZ(-420px) rotateY(${-i * step}deg)`, transition: "transform var(--dur-slow) var(--ease-emphasis)" }}>
            {PRESETS.map((p, j) => (
              <article key={p.k} aria-hidden={j !== i} inert={j !== i} className="hud absolute left-1/2 top-0 w-[min(320px,80vw)] h-[340px] p-6 flex flex-col"
                style={{ backfaceVisibility: "hidden", WebkitBackfaceVisibility: "hidden", transform: `translateX(-50%) rotateY(${j * step}deg) translateZ(420px)`, opacity: j === i ? 1 : 0.35, transition: "opacity var(--dur-base) var(--ease-enter)" }}>
                <p className="telemetry">{String(j + 1).padStart(2, "0")} / {String(n).padStart(2, "0")}</p>
                <h3 className="headline my-3" style={{ fontSize: 30 }}>{p.t}</h3>
                <p className="text-sm flex-1" style={{ color: "var(--ink-muted)" }}>{p.d}</p>
                <p className="telemetry mb-4">{p.tools}</p>
                <button className="btn btn-primary w-fit" disabled={busy} onClick={() => use(p.k)}>Use this preset</button>
              </article>))}
          </div>
        </div>
        <div className="flex items-center gap-3 mt-6">
          <button className="btn" onClick={() => go(-1)} aria-label="Previous preset">←</button>
          <button className="btn" onClick={() => go(1)} aria-label="Next preset">→</button>
          <span className="telemetry" aria-live="polite">{PRESETS[i].t}</span>
        </div>
      </div>
    </section>
  );
}
