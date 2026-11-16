"use client";
/** Anthropic API key panel: the key is sent once to the server, stored encrypted, never shown again (last 4 only). */
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type S = { key_present: boolean; key_source: string; key_last4: string | null; key_edit_allowed: boolean; admin_password_set: boolean;
  spend: { cap_usd: number; spent_usd: number }; provider: string; model: string; fallback_model: string; transport: string };

export function KeyPanel() {
  const [s, setS] = useState<S | null>(null);
  const [key, setKey] = useState("");
  const [admin, setAdmin] = useState("");
  const [cap, setCap] = useState("");
  const [msg, setMsg] = useState<{ tone: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api<S>("/api/settings").then((x) => { setS(x); setCap(String(x.spend.cap_usd)); }).catch((e) => setMsg({ tone: "danger", text: e.message }));
  useEffect(() => { load(); }, []);
  async function run(f: () => Promise<any>, ok: string) {
    setBusy(true); setMsg(null);
    try { const r = await f(); setMsg({ tone: "ok", text: typeof ok === "string" ? ok : JSON.stringify(r) }); setKey(""); await load(); }
    catch (e: any) { setMsg({ tone: "danger", text: e.message }); }
    finally { setBusy(false); }
  }
  if (!s) return <section className="glass p-6"><p className="telemetry">Loading settings…</p>{msg && <p>{msg.text}</p>}</section>;
  return (
    <section className="glass p-6 space-y-5" aria-labelledby="key-h">
      <div>
        <h2 id="key-h" className="display text-2xl">Anthropic API key</h2>
        <p className="text-sm mt-1" style={{ color: "var(--ink-muted)" }}>
          The only paid service. Stored encrypted on this machine; never sent back to the browser. Model {s.model}, fallback {s.fallback_model}.
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-sm max-w-md" data-testid="key-status">
        <dt className="telemetry">Status</dt><dd>{s.key_present ? `set (…${s.key_last4})` : "not set"}</dd>
        <dt className="telemetry">Source</dt><dd>{s.key_source === "settings" ? "Settings (encrypted DB)" : s.key_source === "env" ? ".env fallback" : "none"}</dd>
        <dt className="telemetry">Active LLM</dt><dd>{s.provider}</dd>
      </dl>
      {s.key_edit_allowed ? (
        <form className="flex flex-col gap-3 max-w-md" onSubmit={(e) => { e.preventDefault(); run(() => api("/api/settings/key", { method: "PUT", json: { key }, admin }), "Key saved."); }}>
          <label className="flex flex-col gap-1 text-sm">New key
            <input type="password" className="btn" autoComplete="off" spellCheck={false} placeholder="sk-ant-…" value={key} onChange={(e) => setKey(e.target.value)} data-testid="key-input" /></label>
          {s.admin_password_set && (
            <label className="flex flex-col gap-1 text-sm">Admin password
              <input type="password" className="btn" value={admin} onChange={(e) => setAdmin(e.target.value)} /></label>)}
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={busy || !key} type="submit">Save key</button>
            <button className="btn" type="button" disabled={busy || !s.key_present} data-testid="test-key"
              onClick={() => run(() => api("/api/settings/key/test", { method: "POST", admin }), "Key works: one tiny call succeeded.")}>Test key</button>
            <button className="btn" type="button" disabled={busy || s.key_source !== "settings"}
              onClick={() => run(() => api("/api/settings/key", { method: "DELETE", admin }), "Key removed.")}>Remove</button>
          </div>
        </form>
      ) : <p className="text-sm" style={{ color: "var(--warn)" }}>Key editing is disabled on this deployment (ALLOW_KEY_EDIT=false).</p>}
      <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); run(() => api("/api/settings/spend-cap", { method: "PUT", json: { cap_usd: Number(cap) }, admin }), "Spend cap saved."); }}>
        <label className="flex flex-col gap-1 text-sm">Spend cap (USD)
          <input className="btn w-32" inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} data-testid="cap-input" /></label>
        <p className="text-sm" data-testid="spent">Spent so far: <span className="mono">${s.spend.spent_usd.toFixed(4)}</span> of ${s.spend.cap_usd.toFixed(2)}</p>
        <button className="btn" type="submit" disabled={busy}>Save cap</button>
      </form>
      <p className="text-xs" style={{ color: "var(--ink-muted)" }}>Also set a limit in the Anthropic Console. Spend is stored in the database and survives restarts.</p>
      {msg && <p role="status" style={{ color: `var(--${msg.tone})` }} data-testid="settings-msg">{msg.text}</p>}
    </section>
  );
}
