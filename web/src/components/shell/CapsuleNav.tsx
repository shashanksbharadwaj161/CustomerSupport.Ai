"use client";
/** Top capsule navigation with animated active indicator (Supaste / Sable dock ideas, re-implemented). */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLayoutEffect, useRef, useState } from "react";

export const NAV = [
  { href: "/", label: "Home" },
  { href: "/studio/", label: "Studio" },
  { href: "/call/", label: "Live Call" },
  { href: "/knowledge/", label: "Knowledge" },
  { href: "/logs/", label: "Call Logs" },
  { href: "/settings/", label: "Settings" },
];

export function CapsuleNav() {
  const path = usePathname() || "/";
  const wrap = useRef<HTMLDivElement>(null);
  const [ind, setInd] = useState<{ left: number; width: number } | null>(null);
  const active = NAV.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href.replace(/\/$/, ""))))?.href;
  useLayoutEffect(() => {
    const el = wrap.current?.querySelector<HTMLElement>(`[data-href="${active}"]`);
    if (el && wrap.current) setInd({ left: el.offsetLeft, width: el.offsetWidth });
  }, [active, path]);
  return (
    <nav aria-label="Main" className="glass relative flex items-center gap-1 p-1 overflow-x-auto max-w-full" style={{ borderRadius: "var(--radius-pill)" }} ref={wrap}>
      {ind && <span aria-hidden="true" className="absolute top-1 bottom-1" style={{
        left: ind.left, width: ind.width, borderRadius: "var(--radius-pill)", background: "var(--surface-raised)",
        boxShadow: "var(--glow-soft)", border: "1px solid var(--line-strong)",
        transition: "left var(--dur-base) var(--ease-enter), width var(--dur-base) var(--ease-enter)" }} />}
      {NAV.map((n) => (
        <Link key={n.href} href={n.href} data-href={n.href} aria-current={n.href === active ? "page" : undefined}
          className="relative z-10 whitespace-nowrap px-3 py-1.5 text-sm"
          style={{ color: n.href === active ? "var(--ink)" : "var(--ink-muted)", borderRadius: "var(--radius-pill)" }}>
          {n.label}
        </Link>
      ))}
    </nav>
  );
}
