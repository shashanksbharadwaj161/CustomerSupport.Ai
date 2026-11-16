"use client";
/** Shared-password login (only when the server has ADMIN_PASSWORD set). */
import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [need, setNeed] = useState<boolean | null>(null);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<{ required: boolean; ok: boolean }>("/api/auth/status").then((s) => setNeed(s.required && !s.ok)).catch(() => setNeed(false));
  }, []);
  if (need === null) return null;
  if (!need) return <>{children}</>;
  return (
    <main id="main" className="px-[var(--gutter)]"><form className="glass max-w-sm mx-auto mt-20 p-6 space-y-4" onSubmit={async (e) => {
      e.preventDefault(); setErr(null);
      try { const r = await api<{ token: string }>("/api/auth/login", { method: "POST", json: { password: pw } }); setToken(r.token); setNeed(false); }
      catch (x: any) { setErr(x.message); }
    }}>
      <h1 className="display text-3xl">Sign in</h1>
      <p className="text-sm" style={{ color: "var(--ink-muted)" }}>This demo is password protected.</p>
      <label className="flex flex-col gap-1 text-sm">Password
        <input type="password" className="btn" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" /></label>
      {err && <p role="alert" style={{ color: "var(--danger)" }}>{err}</p>}
      <button className="btn btn-primary" type="submit">Enter</button>
    </form></main>
  );
}
