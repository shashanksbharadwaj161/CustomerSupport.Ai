"use client";
/** Passcode login. Share mode has two roles: visitor (calls only) and admin (Studio, Knowledge, Logs, Settings). */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";

type AuthState = { role: "visitor" | "admin" | null; visitorMode: boolean; share: boolean; required: boolean };
const AuthCtx = createContext<{ auth: AuthState; refresh: () => Promise<void> } | null>(null);
export const useAuth = () => useContext(AuthCtx)!;

export function PasscodeForm({ title, hint, onDone }: { title: string; hint: string; onDone: () => void }) {
  const [pc, setPc] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <main id="main" className="px-[var(--gutter)]">
      <form className="glass max-w-sm mx-auto mt-20 p-6 space-y-4" onSubmit={async (e) => {
        e.preventDefault(); setErr(null);
        try { const r = await api<{ token: string }>("/api/auth/login", { method: "POST", json: { passcode: pc.trim() } }); setToken(r.token); onDone(); }
        catch (x: any) { setErr(x.status === 429 ? "Too many attempts. Wait a minute." : "That passcode did not work."); }
      }}>
        <h1 className="display text-3xl">{title}</h1>
        <p className="text-sm" style={{ color: "var(--ink-muted)" }}>{hint}</p>
        <label className="flex flex-col gap-1 text-sm">Passcode
          <input type="password" className="btn" value={pc} onChange={(e) => setPc(e.target.value)} autoComplete="current-password"
            autoCapitalize="none" autoCorrect="off" spellCheck={false} data-testid="passcode" /></label>
        {err && <p role="alert" style={{ color: "var(--danger)" }} data-testid="passcode-error">{err}</p>}
        <button className="btn btn-primary" type="submit" data-testid="passcode-submit">Enter</button>
      </form>
    </main>
  );
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const refresh = useCallback(async () => {
    try {
      const s = await api<{ required: boolean; ok: boolean; role: AuthState["role"]; visitor_mode: boolean; share: boolean }>("/api/auth/status");
      setAuth({ role: s.ok ? s.role : null, visitorMode: s.visitor_mode, share: s.share, required: s.required });
    } catch { setAuth({ role: "admin", visitorMode: false, share: false, required: false }); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  if (!auth) return null;
  if (auth.required && !auth.role)
    return <PasscodeForm title="Enter passcode" hint="This voice-agent demo is private. Use the passcode you were given with the link." onDone={refresh} />;
  return <AuthCtx.Provider value={{ auth, refresh }}>{children}</AuthCtx.Provider>;
}

/** Wrap admin-only pages: visitors are asked for the separate admin passcode. */
export function AdminGate({ children }: { children: React.ReactNode }) {
  const { auth, refresh } = useAuth();
  if (auth.visitorMode && auth.role !== "admin")
    return <PasscodeForm title="Admin only" hint="Agent Studio, Knowledge, Call Logs and Settings need the admin passcode. Visitors can use Live Call." onDone={refresh} />;
  return <>{children}</>;
}
