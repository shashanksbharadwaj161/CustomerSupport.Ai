"use client";
/** Agent Studio: profiles list, tabbed editor, version history, live system-prompt preview. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell, PageHead } from "@/components/shell/AppShell";
import { AdminGate } from "@/components/shell/AuthGate";
import { Area, Chips, Field, Text } from "@/components/studio/fields";
import { api } from "@/lib/api";
import { gsap, setupMotion } from "@/lib/motion";
import { LANG_NAMES, LANGS, token, type Lang } from "@/lib/tokens";

type Profile = { id: string; name: string; type: string; current_version: number };
type Full = { id: string; name: string; type: string; version: number; config: any; note: string };
type Version = { id: number; version: number; note: string; created_at: number };

const TABS = ["Role", "Persona", "Style", "Guardrails", "Languages", "Voices", "Knowledge", "Tools", "Versions"] as const;
type Tab = (typeof TABS)[number];
const PRESETS = [["bank_support", "Bank support"], ["tourism", "Tourism"], ["ecommerce", "E-commerce"], ["clinic_frontdesk", "Clinic front desk"], ["custom", "Custom"]];
const TOOLS: Record<string, string[]> = { bank_support: ["balance_lookup", "card_block_request"], tourism: ["itinerary_search"], ecommerce: ["order_lookup"], clinic_frontdesk: ["appointment_slots"], custom: [] };

function setPath(obj: any, path: string, value: any) {
  const c = structuredClone(obj); const ks = path.split("."); let o = c;
  for (const k of ks.slice(0, -1)) { o[k] = o[k] ?? {}; o = o[k]; }
  o[ks[ks.length - 1]] = value; return c;
}

export default function Studio() {
  const [list, setList] = useState<Profile[]>([]);
  const [cur, setCur] = useState<Full | null>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [tab, setTab] = useState<Tab>("Role");
  const [versions, setVersions] = useState<Version[]>([]);
  const [prompt, setPrompt] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ tone: string; text: string } | null>(null);
  const [voices, setVoices] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const panel = useRef<HTMLDivElement>(null);
  const dirty = useMemo(() => cur && cfg && JSON.stringify(cur.config) !== JSON.stringify(cfg), [cur, cfg]);

  const loadList = useCallback(() => api<Profile[]>("/api/profiles").then(setList), []);
  const open = useCallback(async (id: string) => {
    const p = await api<Full>(`/api/profiles/${id}`);
    setCur(p); setCfg(p.config); setMsg(null);
    api<Version[]>(`/api/profiles/${id}/versions`).then(setVersions);
    api<{ system_prompt: string }>(`/api/profiles/${id}/prompt`).then((r) => setPrompt(r.system_prompt));
    try { const u = new URL(window.location.href); u.searchParams.set("id", id); window.history.replaceState(null, "", u); } catch {}
  }, []);

  useEffect(() => {
    setupMotion();
    loadList().then(() => {});
    api<Profile[]>("/api/profiles").then((l) => { const q = new URL(window.location.href).searchParams.get("id"); if (l.length) open(q && l.some((x) => x.id === q) ? q : l[0].id); });
    api("/api/voices").then(setVoices).catch(() => {});
    api("/api/knowledge").then(setSources).catch(() => setSources([]));
  }, [loadList, open]);

  // masked tab transition (Zajno idea, re-implemented): clip-path reveal on every tab change
  useEffect(() => {
    if (!panel.current) return;
    gsap.fromTo(panel.current, { clipPath: "inset(0 0 100% 0 round 24px)", opacity: 0.4 },
      { clipPath: "inset(0 0 0% 0 round 24px)", opacity: 1, duration: token.dur("base"), ease: "enter" });
  }, [tab]);

  const set = (path: string, v: any) => setCfg((c: any) => setPath(c, path, v));

  async function save() {
    if (!cur) return;
    try {
      const p = await api<Full>(`/api/profiles/${cur.id}`, { method: "PUT", json: { config: cfg, note: note || "saved in Studio" } });
      setCur(p); setCfg(p.config); setNote(""); setMsg({ tone: "ok", text: `Saved as version ${p.version}.` });
      loadList(); api<Version[]>(`/api/profiles/${cur.id}/versions`).then(setVersions);
      api<{ system_prompt: string }>(`/api/profiles/${cur.id}/prompt`).then((r) => setPrompt(r.system_prompt));
    } catch (e: any) { setMsg({ tone: "danger", text: e.message }); }
  }
  async function create(preset: string) {
    const p = await api<Full>("/api/profiles", { method: "POST", json: { preset } });
    await loadList(); open(p.id);
  }
  async function rollback(v: number) {
    if (!cur) return;
    const p = await api<Full>(`/api/profiles/${cur.id}/rollback`, { method: "POST", json: { version: v } });
    await open(cur.id);
    setMsg({ tone: "ok", text: `Rolled back: new version ${p.version} copies version ${v}.` });
  }

  return (
    <AppShell><AdminGate>
      <PageHead index="02" kicker="Agent Studio" title="Studio"
        sub="Role, persona, style, guardrails, languages, voices, knowledge and tools. Every save is a new version you can roll back."
        aside={<div className="flex flex-wrap gap-2" role="group" aria-label="New agent from preset">
          {PRESETS.map(([k, l]) => <button key={k} className="btn btn-sm" onClick={() => create(k)}>+ {l}</button>)}
        </div>} />
      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <nav aria-label="Agents" className="glass p-3 h-fit">
          <ul className="flex lg:flex-col gap-1 overflow-x-auto">
            {list.map((p) => (
              <li key={p.id}><button className="w-full text-left px-3 py-2 text-sm" style={{ borderRadius: "var(--radius-sm)", background: cur?.id === p.id ? "var(--surface-raised)" : "transparent", color: cur?.id === p.id ? "var(--ink)" : "var(--ink-muted)", boxShadow: cur?.id === p.id ? "inset 2px 0 0 var(--signal)" : undefined }}
                onClick={() => open(p.id)} aria-current={cur?.id === p.id}>
                <div>{p.name}</div><div className="telemetry">{p.type} · v{p.current_version}</div></button></li>))}
          </ul>
        </nav>
        {cfg && cur && (
          <section aria-label="Agent editor" className="space-y-4 min-w-0">
            <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Editor sections">
              {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className="btn" style={{ padding: "6px 14px", borderColor: tab === t ? "var(--signal)" : undefined }} onClick={() => setTab(t)}>{t}</button>)}
            </div>
            <div ref={panel} role="tabpanel" className="glass p-6 space-y-5" data-testid={`tab-${tab}`}>
              {tab === "Role" && <>
                <Field label="Agent name"><Text value={cfg.name} onChange={(v) => set("name", v)} testid="agent-name" /></Field>
                <Field label="Agent type" hint="Changes the role sentence and the allowed tools.">
                  <select className="btn" value={cfg.type} onChange={(e) => { set("type", e.target.value); set("tools", TOOLS[e.target.value]); }}>
                    {PRESETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
                <Field label="Custom role text" hint="Extra role instructions (custom agents especially)."><Area value={cfg.custom_role_text} onChange={(v) => set("custom_role_text", v)} rows={4} /></Field>
              </>}
              {tab === "Persona" && <>
                <div className="grid sm:grid-cols-3 gap-4">
                  <Field label="Persona name"><Text value={cfg.persona.name} onChange={(v) => set("persona.name", v)} /></Field>
                  <Field label="Tone"><Text value={cfg.persona.tone} onChange={(v) => set("persona.tone", v)} /></Field>
                  <Field label="Formality"><select className="btn" value={cfg.persona.formality} onChange={(e) => set("persona.formality", e.target.value)}><option>formal</option><option>neutral</option><option>casual</option></select></Field>
                </div>
                <p className="telemetry">Greeting per language (must say it is an AI assistant: enforced on save)</p>
                {LANGS.map((l) => <Field key={l} label={`Greeting · ${LANG_NAMES[l].native}`}><Text lang={l} value={cfg.persona.greeting?.[l]} onChange={(v) => set(`persona.greeting.${l}`, v)} /></Field>)}
                <p className="telemetry">Politeness per language</p>
                <div className="grid sm:grid-cols-2 gap-4">{(["ja", "hi", "bn", "kn"] as Lang[]).map((l) => <Field key={l} label={LANG_NAMES[l].native}><Text value={cfg.persona.politeness?.[l]} onChange={(v) => set(`persona.politeness.${l}`, v)} /></Field>)}</div>
              </>}
              {tab === "Style" && <>
                <Field label={`Max sentences per turn: ${cfg.response_style.max_sentences}`}><input type="range" min={1} max={4} value={cfg.response_style.max_sentences} onChange={(e) => set("response_style.max_sentences", Number(e.target.value))} /></Field>
                <Field label="Verbosity"><select className="btn" value={cfg.response_style.verbosity} onChange={(e) => set("response_style.verbosity", e.target.value)}><option>short</option><option>medium</option></select></Field>
                <label className="flex gap-2 text-sm"><input type="checkbox" checked={cfg.response_style.confirm_numbers} onChange={(e) => set("response_style.confirm_numbers", e.target.checked)} /> Confirm numbers (read back)</label>
                <label className="flex gap-2 text-sm"><input type="checkbox" checked={cfg.response_style.fillers} onChange={(e) => set("response_style.fillers", e.target.checked)} /> Filler phrases</label>
                <Field label="Readback rules"><Area value={cfg.response_style.readback_rules} onChange={(v) => set("response_style.readback_rules", v)} /></Field>
              </>}
              {tab === "Guardrails" && <>
                <Field label="Allowed topics"><Chips items={cfg.guardrails.allowed_topics} onChange={(v) => set("guardrails.allowed_topics", v)} /></Field>
                <Field label="Forbidden topics"><Chips tone="danger" items={cfg.guardrails.forbidden_topics} onChange={(v) => set("guardrails.forbidden_topics", v)} /></Field>
                <Field label="Banned claims"><Chips tone="danger" items={cfg.guardrails.banned_claims} onChange={(v) => set("guardrails.banned_claims", v)} /></Field>
                <Field label="Escalation triggers"><Chips tone="warn" items={cfg.guardrails.escalation_triggers} onChange={(v) => set("guardrails.escalation_triggers", v)} /></Field>
                <Field label="Required disclaimers (trigger → text)">
                  <div className="space-y-2">{cfg.guardrails.required_disclaimers.map((d: any, i: number) => (
                    <div key={i} className="grid sm:grid-cols-[160px_1fr_auto] gap-2">
                      <Text value={d.trigger} onChange={(v) => set(`guardrails.required_disclaimers`, cfg.guardrails.required_disclaimers.map((x: any, j: number) => j === i ? { ...x, trigger: v } : x))} />
                      <Text value={d.text} onChange={(v) => set(`guardrails.required_disclaimers`, cfg.guardrails.required_disclaimers.map((x: any, j: number) => j === i ? { ...x, text: v } : x))} />
                      <button className="btn" onClick={() => set("guardrails.required_disclaimers", cfg.guardrails.required_disclaimers.filter((_: any, j: number) => j !== i))}>Remove</button>
                    </div>))}
                    <button className="btn" onClick={() => set("guardrails.required_disclaimers", [...cfg.guardrails.required_disclaimers, { trigger: "", text: "" }])}>+ Disclaimer</button></div></Field>
                <Field label="PII rules"><Area value={cfg.guardrails.pii_rules} onChange={(v) => set("guardrails.pii_rules", v)} /></Field>
                <Field label="Refusal style"><Text value={cfg.guardrails.refusal_style} onChange={(v) => set("guardrails.refusal_style", v)} /></Field>
                <div className="grid sm:grid-cols-2 gap-4">
                  <Field label="Input check" hint="local = free keyword/pattern rules; model = adds a Claude check (costs)"><select className="btn" value={cfg.guardrails.input_check} onChange={(e) => set("guardrails.input_check", e.target.value)}><option value="local">local</option><option value="model">local + Claude</option></select></Field>
                  <Field label="Reply check" hint="combined = one Claude check before speaking (default)"><select className="btn" value={cfg.guardrails.reply_check} onChange={(e) => set("guardrails.reply_check", e.target.value)}><option value="combined">combined (Claude)</option><option value="local">local only</option></select></Field>
                </div>
                <p className="telemetry">Handoff message per language</p>
                {LANGS.map((l) => <Field key={l} label={LANG_NAMES[l].native}><Text lang={l} value={cfg.guardrails.handoff_message?.[l]} onChange={(v) => set(`guardrails.handoff_message.${l}`, v)} /></Field>)}
              </>}
              {tab === "Languages" && <>
                <fieldset><legend className="telemetry mb-2">Enabled languages</legend>
                  <div className="flex flex-wrap gap-2">{LANGS.map((l) => {
                    const on = cfg.languages.enabled.includes(l);
                    return <button key={l} lang={l} className={`btn lang-${l}`} aria-pressed={on} style={{ background: on ? "color-mix(in srgb, currentColor 16%, var(--surface-raised))" : undefined, borderColor: on ? "currentColor" : undefined, textDecoration: on ? undefined : "line-through" }}
                      onClick={() => set("languages.enabled", on ? cfg.languages.enabled.filter((x: string) => x !== l) : [...cfg.languages.enabled, l])}>{LANG_NAMES[l].native}</button>;
                  })}</div></fieldset>
                <Field label="Default language"><select className="btn" value={cfg.languages.default} onChange={(e) => set("languages.default", e.target.value)}>{cfg.languages.enabled.map((l: Lang) => <option key={l} value={l}>{LANG_NAMES[l].native}</option>)}</select></Field>
                <label className="flex gap-2 text-sm"><input type="checkbox" checked={cfg.languages.auto_switch} onChange={(e) => set("languages.auto_switch", e.target.checked)} /> Auto-switch language per turn</label>
                <p className="telemetry">Model per language (Sonnet 5.5 fallback if Haiku is weak in a language: decide from eval/results.md)</p>
                <div className="grid sm:grid-cols-5 gap-2">{LANGS.map((l) => (
                  <Field key={l} label={l.toUpperCase()}><select className="btn" value={cfg.languages.llm_model_override?.[l] || ""} onChange={(e) => set(`languages.llm_model_override.${l}`, e.target.value || undefined)}>
                    <option value="">Haiku 5.5</option><option value="claude-sonnet-5-5">Sonnet 5.5</option></select></Field>))}</div>
              </>}
              {tab === "Voices" && <>
                <Field label="Persona set"><select className="btn" value={cfg.voices.persona_set} onChange={(e) => set("voices.persona_set", e.target.value)}>
                  {["warm_female", "calm_male", "energetic_young", "formal_senior", "one_voice_demo"].map((p) => <option key={p}>{p}</option>)}</select></Field>
                {cfg.languages.enabled.map((l: Lang) => (
                  <Field key={l} label={`Voice override · ${LANG_NAMES[l].native}`}>
                    <select className="btn" value={cfg.voices.by_language?.[l] || ""} onChange={(e) => set(`voices.by_language.${l}`, e.target.value || undefined)}>
                      <option value="">from persona set</option>
                      {voices.filter((v) => v.language === l).map((v) => <option key={v.id} value={v.id}>{v.display_name}{v.demo_only ? " (demo only)" : ""}{v.status === "pending" ? " (pending)" : ""}</option>)}
                    </select></Field>))}
                <p className="text-sm" style={{ color: "var(--ink-muted)" }}>Preview voices in Settings → Voices.</p>
              </>}
              {tab === "Knowledge" && <>
                <p className="text-sm" style={{ color: "var(--ink-muted)" }}>Attach crawled websites (Knowledge page).</p>
                <ul className="space-y-2">{sources.map((s) => {
                  const on = cfg.knowledge.source_ids.includes(s.id);
                  return <li key={s.id}><label className="flex gap-2 text-sm"><input type="checkbox" checked={on} onChange={() => set("knowledge.source_ids", on ? cfg.knowledge.source_ids.filter((x: string) => x !== s.id) : [...cfg.knowledge.source_ids, s.id])} />
                    {s.url} <span className="telemetry">{s.status} · {s.chunks} chunks</span></label></li>;
                })}{sources.length === 0 && <li className="telemetry">No sources yet.</li>}</ul>
                <div className="grid sm:grid-cols-3 gap-4">
                  <Field label="Top-k"><input className="btn" type="number" min={1} max={10} value={cfg.knowledge.top_k} onChange={(e) => set("knowledge.top_k", Number(e.target.value))} /></Field>
                  <Field label="Min score"><input className="btn" type="number" step={0.05} min={0} max={1} value={cfg.knowledge.min_score} onChange={(e) => set("knowledge.min_score", Number(e.target.value))} /></Field>
                  <label className="flex gap-2 text-sm items-center"><input type="checkbox" checked={cfg.knowledge.site_brief} onChange={(e) => set("knowledge.site_brief", e.target.checked)} /> Use site brief</label>
                </div>
              </>}
              {tab === "Tools" && <>
                <p className="text-sm" style={{ color: "var(--ink-muted)" }}>Mock tools (fake data). Only tools allowed for the agent type can be enabled (guardrail layer 3).</p>
                {(TOOLS[cfg.type] || []).map((t) => <label key={t} className="flex gap-2 text-sm mono"><input type="checkbox" checked={cfg.tools.includes(t)} onChange={(e) => set("tools", e.target.checked ? [...cfg.tools, t] : cfg.tools.filter((x: string) => x !== t))} /> {t}</label>)}
                {(TOOLS[cfg.type] || []).length === 0 && <p className="telemetry">No tools for this type.</p>}
              </>}
              {tab === "Versions" && <ul className="space-y-2" data-testid="versions">{versions.map((v) => (
                <li key={v.id} className="flex flex-wrap items-center gap-3 text-sm"><span className="mono">v{v.version}</span><span>{v.note}</span>
                  <span className="telemetry">{new Date(v.created_at * 1000).toLocaleString()}</span>
                  {v.version !== cur.version && <button className="btn" style={{ padding: "2px 10px" }} onClick={() => rollback(v.version)}>Roll back to v{v.version}</button>}</li>))}</ul>}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <input className="btn" placeholder="Version note (optional)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Version note" />
              <button className="btn btn-primary" onClick={save} disabled={!dirty} data-testid="save-profile">Save version {cur.version + 1}</button>
              <a className="btn" href={`/call/?profile=${cur.id}`}>Test call</a>
              {dirty && <span className="telemetry" style={{ color: "var(--warn)" }}>unsaved changes</span>}
              {msg && <span role="status" style={{ color: `var(--${msg.tone})` }}>{msg.text}</span>}
            </div>
            <details className="glass p-4"><summary className="telemetry cursor-pointer">System prompt preview (saved version, cached prefix)</summary>
              <pre className="mono text-xs whitespace-pre-wrap mt-3" style={{ color: "var(--ink-muted)" }}>{prompt}</pre></details>
          </section>)}
      </div>
    </AdminGate></AppShell>
  );
}
