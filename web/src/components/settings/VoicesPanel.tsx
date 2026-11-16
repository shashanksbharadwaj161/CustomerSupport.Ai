"use client";
/** Voice picker: per language, 5-second preview, set default for an agent, add a consenting persona clip. */
import { useEffect, useRef, useState } from "react";
import { API_BASE, api, getToken } from "@/lib/api";
import { LANG_NAMES, LANGS, type Lang } from "@/lib/tokens";

type V = { id: string; language: Lang; engine: string; display_name: string; persona_tag?: string; license: string; demo_only: boolean;
  unrated: boolean; status: "ready" | "pending"; user_added: boolean };

export function VoicesPanel() {
  const [voices, setVoices] = useState<V[]>([]);
  const [lang, setLang] = useState<Lang>("en");
  const [profiles, setProfiles] = useState<{ id: string; name: string }[]>([]);
  const [agent, setAgent] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: string; text: string } | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const load = () => api<V[]>("/api/voices").then(setVoices).catch(() => {});
  useEffect(() => { load(); api("/api/profiles").then((p: any) => { setProfiles(p); setAgent(p[0]?.id || ""); }).catch(() => {}); }, []);

  async function preview(v: V) {
    setBusy(v.id); setMsg(null);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const t = getToken(); if (t) headers.Authorization = `Bearer ${t}`;
      const r = await fetch(`${API_BASE}/api/voices/preview`, { method: "POST", headers, body: JSON.stringify({ voice_id: v.id }), credentials: "include" });
      if (!r.ok) throw new Error((await r.json()).detail);
      const url = URL.createObjectURL(await r.blob());
      audio.current?.pause(); audio.current = new Audio(url); await audio.current.play();
      setMsg({ tone: "ok", text: `${v.display_name}: ${r.headers.get("x-audio-seconds")} s preview` });
    } catch (e: any) { setMsg({ tone: "warn", text: e.message }); }
    finally { setBusy(null); }
  }
  async function setDefault(v: V) {
    if (!agent) return;
    const p: any = await api(`/api/profiles/${agent}`);
    p.config.voices.by_language = { ...(p.config.voices.by_language || {}), [v.language]: v.id };
    const s: any = await api(`/api/profiles/${agent}`, { method: "PUT", json: { config: p.config, note: `voice ${v.language} -> ${v.id}` } });
    setMsg({ tone: "ok", text: `Default ${LANG_NAMES[v.language].latin} voice for ${s.name} is now ${v.display_name} (v${s.version}).` });
  }
  async function addClip(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setMsg(null);
    const fd = new FormData(e.currentTarget);
    fd.set("consent", (e.currentTarget.elements.namedItem("consent") as HTMLInputElement).checked ? "true" : "false");
    const headers: Record<string, string> = {}; const t = getToken(); if (t) headers.Authorization = `Bearer ${t}`;
    const r = await fetch(`${API_BASE}/api/voices`, { method: "POST", body: fd, headers, credentials: "include" });
    const j = await r.json();
    if (!r.ok) setMsg({ tone: "danger", text: j.detail }); else { setMsg({ tone: "ok", text: `Added ${j.id} (demo only, ${j.duration_s} s).` }); load(); (e.target as HTMLFormElement).reset(); }
  }

  const list = voices.filter((v) => v.language === lang);
  return (
    <section className="glass p-6 space-y-4" aria-labelledby="voices-h" data-testid="voices-panel">
      <h2 id="voices-h" className="display text-2xl">Voices</h2>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Voice language">
        {LANGS.map((l) => <button key={l} role="tab" aria-selected={l === lang} lang={l} className={`btn lang-${l}`} style={{ opacity: l === lang ? 1 : 0.6 }} onClick={() => setLang(l)}>{LANG_NAMES[l].native}</button>)}
      </div>
      <label className="flex items-center gap-2 text-sm">Set defaults for agent
        <select className="btn" value={agent} onChange={(e) => setAgent(e.target.value)}>{profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <ul className="grid sm:grid-cols-2 gap-3">
        {list.map((v) => (
          <li key={v.id} className="p-4 space-y-2" style={{ border: "1px solid var(--line)", borderRadius: "var(--radius-md)" }} data-testid={`voice-${v.id}`}>
            <div className="flex flex-wrap items-center gap-2"><strong className="text-sm">{v.display_name}</strong>
              {v.demo_only && <span className="badge-demo">demo only</span>}
              <span className="telemetry" style={{ color: v.status === "ready" ? "var(--ok)" : "var(--warn)" }}>{v.status === "ready" ? "ready" : "pending"}</span>
              {v.unrated && <span className="telemetry">unrated</span>}</div>
            <p className="telemetry" style={{ textTransform: "none" }}>{v.engine} · {v.license}{v.persona_tag ? ` · ${v.persona_tag}` : ""}</p>
            <div className="flex flex-wrap gap-2">
              <button className="btn" style={{ padding: "4px 12px" }} onClick={() => preview(v)} disabled={busy === v.id} data-testid={`preview-${v.id}`}>{busy === v.id ? "Synthesizing…" : "Preview"}</button>
              <button className="btn" style={{ padding: "4px 12px" }} onClick={() => setDefault(v)}>Set default</button>
              {v.user_added && <button className="btn" style={{ padding: "4px 12px", color: "var(--danger)" }} onClick={() => api(`/api/voices/${v.id}`, { method: "DELETE" }).then(load)}>Delete</button>}
            </div>
          </li>))}
      </ul>
      {msg && <p role="status" style={{ color: `var(--${msg.tone})` }} data-testid="voices-msg">{msg.text}</p>}
      <details className="pt-2"><summary className="telemetry cursor-pointer">Add a persona reference clip (OmniVoice clone, demo only)</summary>
        <form className="grid sm:grid-cols-2 gap-3 mt-3 text-sm" onSubmit={addClip}>
          <label className="flex flex-col gap-1">Clip (3-10 s)<input className="btn" type="file" name="clip" accept="audio/*" required /></label>
          <label className="flex flex-col gap-1">Language<select className="btn" name="language">{LANGS.map((l) => <option key={l} value={l}>{LANG_NAMES[l].native}</option>)}</select></label>
          <label className="flex flex-col gap-1 sm:col-span-2">Exact transcript of the clip<input className="btn" name="transcript" required /></label>
          <label className="flex flex-col gap-1">Name<input className="btn" name="display_name" /></label>
          <label className="flex flex-col gap-1">Source<select className="btn" name="source"><option value="consenting_speaker">consenting speaker</option><option value="model_generated">model-generated clip</option></select></label>
          <label className="flex gap-2 sm:col-span-2"><input type="checkbox" name="consent" /> The speaker consented to voice cloning, or the clip is model-generated. Never clone a real person without consent.</label>
          <button className="btn btn-primary w-fit" type="submit">Add clip</button>
        </form></details>
    </section>
  );
}
