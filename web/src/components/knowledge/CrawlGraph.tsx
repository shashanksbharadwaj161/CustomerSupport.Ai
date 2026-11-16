"use client";
/** Crawl progress as nodes that fill in, then collapse into the brief (ARQ-01 idea, re-implemented in SVG). */
import { useEffect, useRef } from "react";
import { gsap, setupMotion } from "@/lib/motion";
import { token } from "@/lib/tokens";

export type GNode = { url: string; depth: number; rendered?: boolean };

export function CrawlGraph({ nodes, done, failed }: { nodes: GNode[]; done: boolean; failed: boolean }) {
  const svg = useRef<SVGSVGElement>(null);
  const W = 640, H = 240, cx = W / 2, cy = H / 2;
  const pos = nodes.map((n, i) => {
    const ring = n.depth, perRing = Math.max(1, nodes.filter((m) => m.depth === ring).length);
    const k = nodes.filter((m, j) => m.depth === ring && j < i).length;
    const a = (k / perRing) * Math.PI * 2 + ring * 0.6;
    const r = 34 + ring * 52;
    return { x: cx + Math.cos(a) * r * 1.9, y: cy + Math.sin(a) * r * 0.75 };
  });
  useEffect(() => {
    setupMotion();
    const el = svg.current;
    if (!el) return;
    const last = el.querySelector("g.node:last-of-type");
    if (last) gsap.from(last, { opacity: 0, scale: 0.2, transformOrigin: "center", duration: token.dur("base") });
  }, [nodes.length]);
  useEffect(() => {
    if (!done || !svg.current) return;
    gsap.to(svg.current.querySelectorAll("g.node"), { x: (i: number) => cx - pos[i].x, y: (i: number) => cy - pos[i].y, opacity: 0.15,
      stagger: 0.02, duration: token.dur("slow"), ease: "emphasis" });
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={`Crawl graph: ${nodes.length} pages`} data-testid="crawl-graph">
      {pos.map((p, i) => <line key={`l${i}`} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="var(--line)" />)}
      {nodes.map((n, i) => (
        <g key={n.url} className="node">
          <circle cx={pos[i].x} cy={pos[i].y} r={7} fill={n.rendered ? "var(--signal-alt)" : "var(--signal)"} opacity={0.9} />
          <title>{n.url}</title>
        </g>))}
      <circle cx={cx} cy={cy} r={done ? 22 : 12} fill="none" stroke={failed ? "var(--danger)" : "var(--signal)"} strokeWidth={2}
        style={{ transition: `r var(--dur-slow) var(--ease-emphasis)` }} />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize="10" fill="var(--ink)" fontFamily="var(--font-mono)">{done ? "BRIEF" : failed ? "ERROR" : "SITE"}</text>
    </svg>
  );
}
