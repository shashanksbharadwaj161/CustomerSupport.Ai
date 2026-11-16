"use client";
import Link from "next/link";
import { AuthGate } from "./AuthGate";
import { CapsuleNav } from "./CapsuleNav";
import { StatusBanner } from "./StatusBanner";

export function AppShell({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-40 flex flex-wrap items-center gap-3 justify-between" style={{ padding: "12px var(--gutter)" }}>
        <Link href="/" className="display text-xl" aria-label="ShaOn home">ShaOn<span style={{ color: "var(--signal)" }}>.</span></Link>
        <CapsuleNav />
      </header>
      <StatusBanner />
      <main id="main" className="flex-1 w-full mx-auto" style={{ maxWidth: wide ? "none" : "var(--content-max)", padding: "0 var(--gutter) 48px" }}>
        <AuthGate>{children}</AuthGate>
      </main>
    </div>
  );
}
