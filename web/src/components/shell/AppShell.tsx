"use client";
/**
 * Console shell (design/references.md): desktop = left rail + status strip; phone = status strip + bottom dock.
 * The status strip always shows the mode, the language model actually answering, engine readiness and spend.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "./AuthGate";
import { IconCall, IconHome, IconKnowledge, IconLogs, IconSettings, IconStudio } from "./Icons";

export const NAV = [
  { href: "/", label: "Home", short: "Home", icon: IconHome, admin: false },
  { href: "/call/", label: "Live Call", short: "Call", icon: IconCall, admin: false },
  { href: "/studio/", label: "Studio", short: "Studio", icon: IconStudio, admin: true },
  { href: "/knowledge/", label: "Knowledge", short: "Know", icon: IconKnowledge, admin: true },
  { href: "/logs/", label: "Call Logs", short: "Logs", icon: IconLogs, admin: true },
  { href: "/settings/", label: "Settings", short: "Setup", icon: IconSettings, admin: true },
];

type Health = { mode: "full" | "demo"; reasons: string[]; provider?: string; model?: string | null; local_preview?: boolean;
  exposed?: boolean; spend?: { cap_usd: number; spent_usd: number }; auth_required?: boolean };

function useNav() {
  const path = usePathname() || "/";
  const ctx = useAuth();
  const visitor = !!ctx && ctx.auth.visitorMode && ctx.auth.role !== "admin";
  const items = NAV.filter((n) => !(visitor && n.admin));
  const active = items.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href.replace(/\/$/, ""))))?.href;
  return { items, active, visitor };
}

export function useHealth(intervalMs = 15000) {
  const [h, setH] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => fetch("/api/health").then((r) => r.json()).then((j) => { if (alive) { setH(j); setOffline(false); } })
      .catch(() => alive && setOffline(true));
    load();
    const id = window.setInterval(load, intervalMs);
    return () => { alive = false; window.clearInterval(id); };
  }, [intervalMs]);
  return { h, offline };
}

function Rail() {
  const { items, active } = useNav();
  return (
    <aside className="rail" aria-label="Sections">
      <Link href="/" className="flex flex-col items-center gap-1 py-5" aria-label="ShaOn home" style={{ borderBottom: "1px solid var(--line)" }}>
        <span className="display" style={{ fontSize: 22, letterSpacing: "-0.06em" }}>Sh<span style={{ color: "var(--signal)" }}>.</span></span>
        <span className="telemetry" style={{ fontSize: 9 }}>v0.2</span>
      </Link>
      <nav aria-label="Main" className="flex flex-col py-2">
        {items.map((n, i) => (
          <Link key={n.href} href={n.href} className="rail-link" aria-current={n.href === active ? "page" : undefined}>
            <span className="ix">{String(i).padStart(2, "0")}</span>
            <n.icon size={22} />
            <span>{n.short}</span>
          </Link>
        ))}
      </nav>
      <div className="flex-1" />
      <p aria-hidden="true" className="telemetry text-center pb-5" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", margin: "0 auto", fontSize: 9 }}>
        SHAON / SIGNAL CONSOLE / 5 LANG
      </p>
    </aside>
  );
}

function Dock() {
  const { items, active, visitor } = useNav();
  return (
    <nav aria-label="Main" className={`dock${visitor ? " dock-visitor" : ""}`}>
      {items.map((n) => (
        <Link key={n.href} href={n.href} aria-current={n.href === active ? "page" : undefined}>
          <n.icon size={22} /><span>{n.short}</span>
        </Link>
      ))}
    </nav>
  );
}

function StatusStrip() {
  const { h, offline } = useHealth();
  const { visitor } = useNav();
  const path = usePathname() || "/";
  const section = NAV.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href.replace(/\/$/, ""))))?.label || "";
  const mode = h?.local_preview ? { t: "Local preview", c: "chip-live" } : h?.exposed ? { t: "Shared link", c: "chip-warn" } : { t: "Local", c: "" };
  const llm = !h ? "…" : h.provider === "anthropic" ? h.model || "claude" : h.provider === "fake" ? "fake test model" : "no key: demo replies";
  return (
    <div className="topbar" role="banner">
      <Link href="/" className="display lg:hidden" style={{ fontSize: 18, letterSpacing: "-0.06em" }} aria-label="ShaOn home">ShaOn<span style={{ color: "var(--signal)" }}>.</span></Link>
      <span className="telemetry hidden lg:inline">ShaOn <span className="faint">/</span> <span style={{ color: "var(--ink)" }}>{section}</span></span>
      <span className="flex-1" />
      {offline ? <span className="chip chip-danger" data-testid="demo-banner"><span className="light light-danger" />API offline</span> : (
        <>
          <span className={`chip ${mode.c} hidden sm:inline-flex`}>{mode.t}</span>
          <span className={`chip ${h?.provider === "anthropic" ? "chip-ok" : "chip-warn"}`} title="Language model answering calls" data-testid="status-llm">
            <span className={`light ${h?.provider === "anthropic" ? "light-ok" : "light-warn"}`} />{llm}
          </span>
          {h?.spend && !visitor && (
            <Link href="/settings/#spend" className="chip hidden md:inline-flex" title="Claude spend so far / cap">
              <span className="num">${h.spend.spent_usd.toFixed(2)}</span><span className="faint">/</span><span className="num">${h.spend.cap_usd.toFixed(0)}</span>
            </Link>
          )}
        </>
      )}
    </div>
  );
}

/** Honest list of what is missing (key, models, cap), shown once under the strip. */
function DemoReasons() {
  const { h } = useHealth();
  const { visitor } = useNav();
  if (!h || h.mode === "full" || !h.reasons?.length) return null;
  return (
    <div role="status" data-testid="demo-banner" className="notice notice-warn" style={{ margin: "14px 0 0" }}>
      <span className="light light-warn" style={{ marginTop: 6 }} />
      <span>Demo mode: {h.reasons.join(" · ")}{!visitor && <> · <Link href="/settings/" style={{ textDecoration: "underline" }}>Open Settings</Link></>}</span>
    </div>
  );
}

export function AppShell({ children, wide = false, bare = false }: { children: React.ReactNode; wide?: boolean; bare?: boolean }) {
  const path = usePathname() || "/";
  return (
    <div className="shell console-bg">
      <Rail />
      <div className="min-w-0 flex flex-col">
        <StatusStrip />
        <main id="main" className={`flex-1 w-full min-w-0 with-dock ${bare ? "" : "mx-auto"}`}
          style={bare ? undefined : { maxWidth: wide ? "none" : "var(--content-max)", padding: "0 var(--gutter)" }}>
          {/* route transition: content only (the dock is fixed and must not be inside a transformed box) */}
          <div key={path} className="page-enter">
            {!bare && <DemoReasons />}
            {children}
          </div>
        </main>
      </div>
      <Dock />
    </div>
  );
}

export function PageHead({ index, kicker, title, sub, aside }: { index: string; kicker: string; title: string; sub?: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <header className="page-head">
      <div>
        <p className="kicker"><span className="faint">{index} </span>{kicker}</p>
        <h1 className="page-title">{title}</h1>
        {sub && <p className="page-sub mt-4">{sub}</p>}
      </div>
      {aside && <div className="flex flex-wrap gap-2 items-center">{aside}</div>}
    </header>
  );
}

/** Window-style panel: title bar with index, title, status light and actions. */
export function Module({ index, title, light, actions, children, id, className = "", bodyClass = "", testid }: {
  index?: string; title: string; light?: "ok" | "warn" | "danger" | "live" | "off"; actions?: React.ReactNode; children: React.ReactNode;
  id?: string; className?: string; bodyClass?: string; testid?: string }) {
  const hid = id ? `${id}-h` : undefined;
  return (
    <section className={`module ${className}`} id={id} aria-labelledby={hid} data-testid={testid}>
      <div className="module-head">
        {light && <span className={`light ${light !== "off" ? `light-${light}` : ""}`} />}
        {index && <span className="idx">{index}</span>}
        <h2 id={hid} className="ttl" style={{ font: "inherit", margin: 0 }}>{title}</h2>
        <span className="spacer" />
        {actions}
      </div>
      <div className={`module-body ${bodyClass}`}>{children}</div>
    </section>
  );
}
