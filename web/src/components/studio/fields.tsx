"use client";
/** Small form primitives for the Studio (token-styled, keyboard accessible). */
import { useId, useState } from "react";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="telemetry">{label}</span>
      {children}
      {hint && <span className="text-xs" style={{ color: "var(--ink-faint)" }}>{hint}</span>}
    </label>
  );
}

export const inputCls = "btn w-full";
export const inputStyle: React.CSSProperties = { borderRadius: "var(--radius-md)", justifyContent: "flex-start" };

export function Text({ value, onChange, lang, placeholder, testid }: { value: string; onChange: (v: string) => void; lang?: string; placeholder?: string; testid?: string }) {
  return <input className={inputCls} style={inputStyle} lang={lang} value={value ?? ""} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} data-testid={testid} />;
}

export function Area({ value, onChange, lang, rows = 3 }: { value: string; onChange: (v: string) => void; lang?: string; rows?: number }) {
  return <textarea className={inputCls} style={{ ...inputStyle, minHeight: rows * 26, resize: "vertical" }} lang={lang} rows={rows} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
}

/** Editable list of strings shown as chips with a micro-animation on add/remove. */
export function Chips({ items, onChange, placeholder, tone = "signal" }: { items: string[]; onChange: (v: string[]) => void; placeholder?: string; tone?: string }) {
  const [draft, setDraft] = useState("");
  const id = useId();
  const add = () => { const v = draft.trim(); if (v && !items.includes(v)) onChange([...items, v]); setDraft(""); };
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-wrap gap-2" aria-labelledby={id}>
        {items.map((x) => (
          <li key={x} className="fade-in inline-flex items-center gap-1 text-xs px-3 py-1" style={{ borderRadius: "var(--radius-pill)", border: `1px solid color-mix(in srgb, var(--${tone}) 50%, transparent)`, color: `var(--${tone})` }}>
            {x}
            <button type="button" aria-label={`Remove ${x}`} className="ml-1" onClick={() => onChange(items.filter((i) => i !== x))}>×</button>
          </li>))}
      </ul>
      <div className="flex gap-2">
        <input id={id} className={inputCls} style={inputStyle} value={draft} placeholder={placeholder} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <button type="button" className="btn" onClick={add}>Add</button>
      </div>
    </div>
  );
}
