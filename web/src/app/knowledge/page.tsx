"use client";
/** Knowledge: URL drop zone -> crawl progress (SSE, polling fallback) -> pages, chunks, brief, test question. */
import { useCallback, useEffect, useRef, useState } from "react";
import { CrawlGraph, type GNode } from "@/components/knowledge/CrawlGraph";
import { AppShell } from "@/components/shell/AppShell";
import { API_BASE, api, getToken } from "@/lib/api";

type Source = { id: string; url: string; status: string; pages: number; chunks: number; brief_status?: string; embedder?: string; error?: string; profile_id?: string };
type Ev = { id: number; kind: string; data: any };

export default function Knowledge() {
  const [sources, setSources] = useState<Source[]>([]);
  const [profiles, setProfiles] = useState<{ id: string; name: string }[]>([]);
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState(3);
  const [maxPages, setMaxPages] = useState(50);
  const [render, setRender] = useState("auto");
  const [attach, setAttach] = useState("");
  const [perm, setPerm] = useState(false);
  const [drag, setDrag] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [mode, setMode] = useState<"sse" | "poll">("sse");
  const [q, setQ] = useState("");
  const [ans, setAns] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const stopRef = useRef<() => void>(() => {});

  const load = useCallback(() => api<Source[]>("/api/knowledge").then(setSources).catch(() => {}), []);
  useEffect(() => {
    load(); api("/api/profiles").then(setProfiles).catch(() => {});
    // Quick Tunnels do not support SSE (it may just buffer silently): poll unless we are on this machine
    try {
      const u = new URL(window.location.href);
      const local = ["localhost", "127.0.0.1"].includes(u.hostname);
      if (u.searchParams.get("poll") === "1" || (!local && u.searchParams.get("sse") !== "1")) setMode("poll");
    } catch {}
    // suggest the local demo site
    setUrl(`${window.location.origin}/demo-sites/lotus-bank/`);
  }, [load]);

  const follow = useCallback((sid: string, m: "sse" | "poll") => {
    stopRef.current(); setEvents([]);
    const refresh = () => { api(`/api/knowledge/${sid}`).then(setDetail).catch(() => {}); load(); };
    refresh();
    if (m === "sse" && !getToken()) {
      const es = new EventSource(`${API_BASE}/api/knowledge/${sid}/events`, { withCredentials: true });
      es.onmessage = () => {};
      const on = (e: MessageEvent) => { const ev = JSON.parse(e.data); if (ev.kind) setEvents((x) => [...x, ev]); if (["done", "error", "brief"].includes(ev.kind)) refresh(); };
      ["started", "robots", "page", "skipped", "warning", "cleaned", "chunked", "embedded", "brief", "done", "error"].forEach((k) => es.addEventListener(k, on as any));
      es.addEventListener("end", () => { es.close(); refresh(); });
      es.onerror = () => { es.close(); setMode("poll"); follow(sid, "poll"); }; // tunnels without SSE -> polling
      stopRef.current = () => es.close();
      return;
    }
    let after = 0, alive = true;
    const tick = async () => {
      if (!alive) return;
      try {
        const r = await api<{ status: string; events: Ev[] }>(`/api/knowledge/${sid}/events?mode=poll&after=${after}`);
        if (r.events.length) { after = r.events[r.events.length - 1].id; setEvents((x) => [...x, ...r.events]); }
        if (r.status === "ready" || r.status === "error") { refresh(); return; }
      } catch {}
      window.setTimeout(tick, 800);
    };
    tick();
    stopRef.current = () => { alive = false; };
  }, [load]);

  useEffect(() => () => stopRef.current(), []);
  useEffect(() => { if (sel) follow(sel, mode); }, [sel]); // eslint-disable-line react-hooks/exhaustive-deps

  async function start() {
    setErr(null);
    try {
      const r = await api<{ id: string }>("/api/knowledge", { method: "POST", json: { url, permission_confirmed: perm, profile_id: attach || null,
        limits: { max_depth: depth, max_pages: maxPages, render_js: render } } });
      setSel(r.id); follow(r.id, mode); load();
    } catch (e: any) { setErr(e.message); }
  }
  async function ask() {
    if (!sel || !q) return;
    setAns({ loading: true });
    try { setAns(await api(`/api/knowledge/${sel}/ask`, { method: "POST", json: { question: q } })); } catch (e: any) { setAns({ error: e.message }); }
  }

  const nodes: GNode[] = events.filter((e) => e.kind === "page").map((e) => ({ url: e.data.url, depth: e.data.depth, rendered: e.data.rendered }));
  const done = events.some((e) => e.kind === "done") || detail?.status === "ready";
  const failed = events.some((e) => e.kind === "error") || detail?.status === "error";

  return (
    <AppShell>
      <h1 className="display my-6" style={{ fontSize: "clamp(40px, 7vw, 104px)" }}>Knowledge</h1>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="space-y-6 min-w-0">
          <div className={`glass p-6 space-y-4`} style={{ borderColor: drag ? "var(--signal)" : undefined, boxShadow: drag ? "var(--glow-strong)" : undefined,
            transition: "box-shadow var(--dur-base) var(--ease-enter), border-color var(--dur-base) var(--ease-enter)" }}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); const t = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain"); if (t) setUrl(t.trim().split("\n")[0]); }}
            data-testid="dropzone">
            <p className="telemetry">Drop a link here or type it</p>
            <input className="btn w-full" style={{ borderRadius: "var(--radius-md)", fontSize: 18 }} value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Website URL" data-testid="kb-url" />
            <div className="flex flex-wrap gap-4 text-sm items-end">
              <label className="flex flex-col gap-1">Depth<input className="btn w-20" type="number" min={0} max={5} value={depth} onChange={(e) => setDepth(Number(e.target.value))} /></label>
              <label className="flex flex-col gap-1">Max pages<input className="btn w-24" type="number" min={1} max={200} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} /></label>
              <label className="flex flex-col gap-1">JavaScript<select className="btn" value={render} onChange={(e) => setRender(e.target.value)}><option value="auto">render when needed</option><option value="always">always render</option><option value="never">never</option></select></label>
              <label className="flex flex-col gap-1">Attach to agent<select className="btn" value={attach} onChange={(e) => setAttach(e.target.value)}><option value="">none</option>{profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
            </div>
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={perm} onChange={(e) => setPerm(e.target.checked)} data-testid="kb-perm" />
              I own this site or have permission to crawl it. Same domain only; robots.txt is respected.</label>
            <div className="flex gap-3 items-center"><button className="btn btn-primary" disabled={!perm || !url} onClick={start} data-testid="kb-start">Crawl</button>
              <span className="telemetry">progress via {mode === "sse" ? "live stream (SSE)" : "polling"}</span></div>
            {err && <p role="alert" style={{ color: "var(--danger)" }}>{err}</p>}
          </div>
          {sel && detail && (
            <div className="glass p-6 space-y-5" data-testid="kb-detail">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><p className="mono text-sm break-all">{detail.url}</p>
                  <p className="telemetry" data-testid="kb-status">{detail.status} · {detail.pages} pages · {detail.chunks} chunks · {detail.embedder || "-"}</p></div>
                <div className="flex gap-2">
                  <button className="btn" onClick={() => api(`/api/knowledge/${sel}/recrawl`, { method: "POST" }).then(() => follow(sel, mode))}>Re-crawl</button>
                  <button className="btn" style={{ color: "var(--danger)" }} onClick={() => api(`/api/knowledge/${sel}`, { method: "DELETE" }).then(() => { setSel(null); setDetail(null); load(); })}>Delete</button></div>
              </div>
              <CrawlGraph nodes={nodes} done={done} failed={failed} />
              {detail.error && <p style={{ color: "var(--danger)" }}>{detail.error}</p>}
              <div>
                <h2 className="display text-xl mb-2">Site brief</h2>
                {detail.brief_text ? <pre className="text-sm whitespace-pre-wrap">{detail.brief_text}</pre>
                  : <p className="text-sm" style={{ color: "var(--warn)" }}>{detail.brief_status || "pending"}. Small sites still go fully into the agent prompt.</p>}
              </div>
              <div>
                <h2 className="display text-xl mb-2">Ask a test question</h2>
                <div className="flex gap-2"><input className="btn flex-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. শনিবার শাখা কখন খোলে?" aria-label="Test question" data-testid="kb-question" />
                  <button className="btn btn-primary" onClick={ask} disabled={!q || detail.status !== "ready"} data-testid="kb-ask">Ask</button></div>
                {ans?.loading && <p className="telemetry mt-2">searching…</p>}
                {ans?.error && <p style={{ color: "var(--danger)" }}>{ans.error}</p>}
                {ans?.passages && <div className="mt-3 space-y-2" data-testid="kb-answer">
                  {ans.answer ? <p>{ans.answer}</p> : <p className="text-sm" style={{ color: "var(--warn)" }}>{ans.note}</p>}
                  {ans.passages.map((p: any, i: number) => <div key={i} className="text-sm border-l-2 pl-3" style={{ borderColor: "var(--line-strong)" }}>
                    <p className="telemetry" style={{ textTransform: "none" }}>{p.score} · <a className="underline" href={p.url} target="_blank" rel="noreferrer">{p.title}</a></p><p>{p.text.slice(0, 280)}</p></div>)}
                  <p className="telemetry">retrieval {ans.retrieval_ms} ms</p></div>}
              </div>
              <details><summary className="telemetry cursor-pointer">Pages ({detail.pages_list?.length})</summary>
                <ul className="text-sm mt-2 space-y-1">{detail.pages_list?.map((p: any) => <li key={p.url} className="mono break-all">{p.rendered ? "JS " : ""}d{p.depth} · {p.title} · {p.chars} chars</li>)}</ul></details>
              <details><summary className="telemetry cursor-pointer">Chunk preview</summary>
                <ul className="text-sm mt-2 space-y-2">{detail.chunk_preview?.map((c: any) => <li key={c.id}><span className="telemetry" style={{ textTransform: "none" }}>{c.url}</span><p>{c.text.slice(0, 200)}</p></li>)}</ul></details>
              <details><summary className="telemetry cursor-pointer">Event log ({events.length})</summary>
                <ol className="mono text-xs mt-2 space-y-1">{events.map((e) => <li key={e.id}>{e.kind} {JSON.stringify(e.data).slice(0, 140)}</li>)}</ol></details>
            </div>)}
        </section>
        <aside className="glass p-4 h-fit space-y-2" aria-label="Sources">
          <h2 className="telemetry">Sources</h2>
          {sources.map((s) => <button key={s.id} className="block w-full text-left px-3 py-2 text-sm" style={{ borderRadius: "var(--radius-md)", background: sel === s.id ? "var(--surface-raised)" : "transparent" }} onClick={() => setSel(s.id)}>
            <div className="break-all">{s.url}</div><div className="telemetry">{s.status} · {s.chunks} chunks</div></button>)}
          {sources.length === 0 && <p className="text-sm" style={{ color: "var(--ink-muted)" }}>No sources yet. Try the demo site prefilled on the left.</p>}
        </aside>
      </div>
    </AppShell>
  );
}
