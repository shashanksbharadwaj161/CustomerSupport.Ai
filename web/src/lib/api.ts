"use client";
/** API client. Same-origin by default (FastAPI serves the UI); NEXT_PUBLIC_API_URL for a split frontend. */
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const TOKEN_KEY = "shaon.token";

export function getToken(): string | null {
  try { return window.localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { if (t) window.localStorage.setItem(TOKEN_KEY, t); else window.localStorage.removeItem(TOKEN_KEY); } catch {}
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown; admin?: string } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  if (opts.admin) headers["X-Admin-Password"] = opts.admin;
  let body = opts.body;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  const r = await fetch(API_BASE + path, { ...opts, headers, body, credentials: "include" });
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    const d = data as any;
    throw new ApiError(r.status, d && typeof d === "object" ? String(d.detail ?? d.error ?? JSON.stringify(d)) : String(data));
  }
  return data as T;
}

export function wsUrl(path: string): string {
  const base = API_BASE || window.location.origin;
  const u = new URL(path, base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  const t = getToken();
  if (t) u.searchParams.set("token", t);
  return u.toString();
}
