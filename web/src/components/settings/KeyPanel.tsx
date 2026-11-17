"use client";
/**
 * Settings core: Anthropic key, model selection, spend cap. One data load (/api/settings), three modules.
 * - The key is sent once, stored encrypted server-side, never returned (last 4 only). Never asked for anywhere else.
 * - Model: catalog cached from Anthropic's docs; "Refresh from my account" lists this key's live models (free Models API).
 *   An explicit ID needs the "use this exact ID" tick and stays "unverified" until Test key or a call succeeds.
 * - Test key makes ONE tiny real call with the selected model, only when pressed.
 */
import { useCallback, useEffect, useState } from "react";
import { Module } from "@/components/shell/AppShell";
import { IconEye, IconKey, IconRefresh } from "@/components/shell/Icons";
import { api } from "@/lib/api";

type CatalogModel = { id: string; name: string; note: string; in: number | null; out: number | null; context: string | null; live?: boolean };
type S = {
  key_present: boolean; key_source: "settings" | "env" | "none"; key_last4: string | null; key_edit_allowed: boolean;
  admin_password_set: boolean; local_preview: boolean; share: boolean; provider: string;
  model: string; model_source: string; model_known: boolean; fallback_model: string; fallback_source: string; fallback_known: boolean;
  active_model: string | null; catalog: CatalogModel[]; catalog_source: string; live_listed_at: string | null; live_count: number;
  spend: { cap_usd: number; spent_usd: number; default_cap_usd: number; cap_source: string; notice: string | null; blocked: boolean };
};
type Msg = { tone: "ok" | "danger" | "warn"; text: string } | null;

export function KeyPanel() {
  const [s, setS] = useState<S | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const load = useCallback(() => api<S>("/api/settings").then((x) => { setS(x); setLoadErr(null); }).catch((e) => setLoadErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (loadErr) return <p className="notice notice-danger" role="alert">Could not load settings: {loadErr}</p>;
  if (!s) return <div className="grid gap-4">{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 180 }} />)}</div>;
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <KeyModule s={s} reload={load} />
      <SpendModule s={s} reload={load} />
      <div className="xl:col-span-2"><ModelModule s={s} reload={load} /></div>
    </div>
  );
}

function useRun(reload: () => Promise<unknown>) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);
  const run = async (name: string, f: () => Promise<any>, ok: (r: any) => string) => {
    setBusy(name); setMsg(null);
    try { const r = await f(); await reload(); setMsg({ tone: "ok", text: ok(r) }); return r; }  // status first, then the message
    catch (e: any) { setMsg({ tone: "danger", text: e.message }); return null; }
    finally { setBusy(null); }
  };
  return { busy, msg, setMsg, run };
}

function KeyModule({ s, reload }: { s: S; reload: () => Promise<unknown> }) {
  const [key, setKey] = useState("");
  const [show, setShow] = useState(false);
  const [admin, setAdmin] = useState("");
  const [confirmRemove, setConfirmRemove] = useState(false);
  const { busy, msg, run } = useRun(reload);
  const source = s.key_source === "settings" ? "Settings (encrypted on this PC)" : s.key_source === "env" ? ".env file (fallback)" : "none";
  return (
    <Module index="01" title="Anthropic API key" id="key" light={s.key_present ? "ok" : "warn"}
      actions={<span className={`chip ${s.key_present ? "chip-ok" : "chip-warn"}`}>{s.key_present ? "configured" : "not set"}</span>}>
      <dl className="rows" data-testid="key-status">
        <dt>Status</dt><dd>{s.key_present ? <span className="num">sk-ant-••••••••{s.key_last4}</span> : "Not set: calls get a fixed demo-mode notice"}</dd>
        <dt>Source</dt><dd>{source}</dd>
        <dt>Answering</dt><dd>{s.provider === "anthropic" ? <span className="mono">{s.active_model}</span> : s.provider === "fake" ? "fake test model (test mode)" : "nothing (demo mode)"}</dd>
      </dl>
      {s.key_edit_allowed ? (
        <form className="grid gap-3 mt-5" autoComplete="off"
          onSubmit={(e) => { e.preventDefault(); const k = key.trim(); setKey("");  // clear the field immediately
            run("save", () => api("/api/settings/key", { method: "PUT", json: { key: k }, admin }), (r) => `Key saved (ends in ${r.key_last4}). It is encrypted on this PC and never shown again.`); }}>
          <label className="label" htmlFor="key-input">{s.key_present ? "Replace key" : "Paste your key"}</label>
          <div className="flex gap-2">
            <input id="key-input" type={show ? "text" : "password"} autoComplete="off" spellCheck={false} placeholder="sk-ant-…" value={key}
              onChange={(e) => setKey(e.target.value)} data-testid="key-input" style={{ fontFamily: "var(--font-mono)" }} />
            <button type="button" className="btn" aria-pressed={show} aria-label={show ? "Hide key" : "Show key"} onClick={() => setShow((v) => !v)}><IconEye size={18} /></button>
          </div>
          {s.admin_password_set && (
            <label className="label">Admin passcode<input type="password" value={admin} onChange={(e) => setAdmin(e.target.value)} autoComplete="off" /></label>)}
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={!!busy || key.trim().length < 20} type="submit" data-testid="save-key"><IconKey size={18} />{s.key_present ? "Replace key" : "Save key"}</button>
            <button className="btn" type="button" disabled={!!busy || !s.key_present || s.provider !== "anthropic"} data-testid="test-key"
              onClick={() => run("test", () => api("/api/settings/key/test", { method: "POST", admin }), (r) => `Key works: ${r.model} answered "${r.reply}".`)}>
              {busy === "test" ? "Testing…" : "Test key"}</button>
            {s.key_source === "settings" && (
              <button className="btn btn-danger" type="button" disabled={!!busy} data-testid="remove-key"
                onClick={() => { if (!confirmRemove) { setConfirmRemove(true); return; } setConfirmRemove(false); run("remove", () => api("/api/settings/key", { method: "DELETE", admin }), (r) => r.key_present ? "Removed from Settings. A key in .env still applies." : "Key removed. Calls are back in demo mode."); }}>
                {confirmRemove ? "Confirm remove" : "Remove"}</button>)}
          </div>
          <p className="hint">Test key makes one tiny paid call (a few tokens) with the selected model, only when you press it. Also set a monthly spend limit for this key in the Anthropic Console.</p>
        </form>
      ) : (
        <p className="notice notice-warn mt-5">Key editing is locked while ShaOn is shared by link. Stop sharing and open ShaOn-Local.bat to change it.</p>
      )}
      {msg && <p role="status" className={`notice notice-${msg.tone} mt-4`} data-testid="settings-msg">{msg.text}</p>}
    </Module>
  );
}

function SpendModule({ s, reload }: { s: S; reload: () => Promise<unknown> }) {
  const [cap, setCap] = useState(String(s.spend.cap_usd));
  const { busy, msg, run } = useRun(reload);
  useEffect(() => { setCap(String(s.spend.cap_usd)); }, [s.spend.cap_usd]);
  const pct = s.spend.cap_usd > 0 ? Math.min(100, (s.spend.spent_usd / s.spend.cap_usd) * 100) : 100;
  return (
    <Module index="02" title="Spend cap" id="spend" light={s.spend.blocked ? "danger" : pct > 80 ? "warn" : "ok"}
      actions={<span className="num">{pct.toFixed(0)}%</span>}>
      <p className="display" style={{ fontSize: 40 }}><span className="num" style={{ fontFamily: "inherit" }}>${s.spend.spent_usd.toFixed(2)}</span>
        <span className="faint" style={{ fontSize: 22 }}> / ${s.spend.cap_usd.toFixed(2)}</span></p>
      <div className="meter mt-3" aria-hidden="true"><span style={{ width: `${pct}%`, background: s.spend.blocked ? "var(--danger)" : pct > 80 ? "var(--warn)" : "var(--signal)" }} /></div>
      <p className="text-sm mt-2" data-testid="spent">Spent so far: <span className="num">${s.spend.spent_usd.toFixed(4)}</span> of ${s.spend.cap_usd.toFixed(2)}</p>
      {s.spend.notice && <p className="notice notice-info mt-3" role="status">{s.spend.notice}</p>}
      {s.spend.blocked && <p className="notice notice-danger mt-3" role="status">The cap is reached: Claude calls are stopped until you raise it.</p>}
      <form className="flex flex-wrap items-end gap-3 mt-5" onSubmit={(e) => { e.preventDefault(); run("cap", () => api("/api/settings/spend-cap", { method: "PUT", json: { cap_usd: Number(cap) } }), () => "Spend cap saved."); }}>
        <label className="label" style={{ width: 160 }}>Cap (USD)
          <input inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} data-testid="cap-input" /></label>
        <button className="btn btn-primary" type="submit" disabled={!!busy || cap.trim() === "" || isNaN(Number(cap))}>Save cap</button>
        <span className="hint">Default {s.spend.default_cap_usd.toFixed(0)} USD · {s.spend.cap_source === "user" ? "set by you" : "default"} · history is never erased</span>
      </form>
      {msg && <p role="status" className={`notice notice-${msg.tone} mt-4`}>{msg.text}</p>}
    </Module>
  );
}

function price(m: CatalogModel) {
  return m.in == null ? "price unknown: capped at the highest rate" : `$${m.in.toFixed(2)} in · $${(m.out ?? 0).toFixed(2)} out / MTok`;
}

function ModelModule({ s, reload }: { s: S; reload: () => Promise<unknown> }) {
  const [model, setModel] = useState(s.model);
  const [fallback, setFallback] = useState(s.fallback_model || "");
  const [custom, setCustom] = useState("");
  const [allowUnlisted, setAllowUnlisted] = useState(false);
  const { busy, msg, run } = useRun(reload);
  useEffect(() => { setModel(s.model); setFallback(s.fallback_model || ""); }, [s.model, s.fallback_model]);
  const chosen = custom.trim() || model;
  const dirty = chosen !== s.model || fallback !== (s.fallback_model || "");
  const listed = s.catalog.some((m) => m.id === chosen);
  return (
    <Module index="03" title="Language model" id="model" light={s.model_known ? "ok" : "warn"}
      actions={<span className="hidden md:inline">{s.model}</span>}>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <p className="label mb-2">Main model (live replies, guard checks, site briefs)</p>
          <p className="hint mb-3">List and prices: {s.catalog_source}. &quot;In your account&quot; marks models your key can use (after Refresh).</p>
          <div role="radiogroup" aria-label="Main model" className="grid gap-2 sm:grid-cols-2" data-testid="model-list">
            {s.catalog.map((m) => {
              const on = !custom.trim() && model === m.id;
              return (
                <button key={m.id} type="button" role="radio" aria-checked={on} onClick={() => { setCustom(""); setModel(m.id); }}
                  className="model-card" data-testid={`model-${m.id}`}>
                  <span className="flex items-center gap-2 w-full">
                    <span className="font-semibold">{m.name}</span><span className="flex-1" />
                    {s.model === m.id && <span className="chip chip-live">active</span>}
                    {m.live && <span className="chip chip-ok">in your account</span>}
                  </span>
                  <span className="mono faint" style={{ fontSize: 12 }}>{m.id}</span>
                  <span className="muted" style={{ fontSize: 13 }}>{m.note}</span>
                  <span className="telemetry" style={{ fontSize: 10, textTransform: "none", letterSpacing: 0 }}>{price(m)}{m.context ? ` · ${m.context} context` : ""}</span>
                </button>);
            })}
          </div>
        </div>
        <div className="grid gap-4 content-start">
          <dl className="rows">
            <dt>Active</dt><dd className="mono" data-testid="active-model">{s.model}{!s.model_known && <span className="chip chip-warn ml-2">unverified</span>}</dd>
            <dt>Fallback</dt><dd className="mono">{s.fallback_model || "none"}</dd>
            <dt>Source</dt><dd>{s.model_source === "settings" ? "saved in Settings" : s.model_source === "env" ? "LLM_MODEL in .env" : "default"}</dd>
            <dt>Live list</dt><dd>{s.live_listed_at ? `${s.live_count} models · ${s.live_listed_at.replace("T", " ").slice(0, 16)}` : "not loaded"}</dd>
          </dl>
          <label className="label">Fallback model
            <select value={fallback} onChange={(e) => setFallback(e.target.value)} data-testid="fallback-select">
              <option value="">None</option>
              {s.catalog.filter((m) => m.id !== chosen).map((m) => <option key={m.id} value={m.id}>{m.name} · {m.id}</option>)}
            </select></label>
          <p className="hint">Used once when the main model is unavailable for your key, overloaded, or declines, and only before anything was spoken. Per-language overrides in Agent Studio take precedence.</p>
          <label className="label">Or an exact model ID
            <input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="claude-…" spellCheck={false} data-testid="custom-model" style={{ fontFamily: "var(--font-mono)" }} /></label>
          {custom.trim() && !listed && (
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={allowUnlisted} onChange={(e) => setAllowUnlisted(e.target.checked)} />
              <span>Use this exact ID although it is not in the list (saved as unverified; Test key checks it; priced at the highest known rate for the cap).</span></label>)}
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" type="button" disabled={!!busy || !dirty || (custom.trim() !== "" && !listed && !allowUnlisted)} data-testid="save-model"
              onClick={() => run("model", () => api("/api/settings/model", { method: "PUT", json: { model: chosen, fallback_model: fallback, allow_unlisted: allowUnlisted } }),
                (r) => `Saved. New calls use ${r.model}${r.fallback_model ? ` (fallback ${r.fallback_model})` : ""}.`).then((r) => { if (r) setCustom(""); })}>
              Save model</button>
            <button className="btn" type="button" disabled={!!busy || s.provider !== "anthropic"} data-testid="refresh-models"
              onClick={() => run("refresh", () => api("/api/settings/models/refresh", { method: "POST" }), (r) => `Loaded ${r.live_count} models from your account.`)}>
              <IconRefresh size={18} />{busy === "refresh" ? "Loading…" : "Refresh from my account"}</button>
          </div>
          {s.provider !== "anthropic" && <p className="hint">Refresh needs a key (it is a free model-list request, no tokens).</p>}
        </div>
      </div>
      {msg && <p role="status" className={`notice notice-${msg.tone} mt-4`} data-testid="model-msg">{msg.text}</p>}
    </Module>
  );
}
