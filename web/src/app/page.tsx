import { Hero } from "@/components/landing/Hero";
import { CapsuleNav } from "@/components/shell/CapsuleNav";

export default function Landing() {
  return (
    <>
      <header className="fixed top-0 inset-x-0 z-40 flex justify-center" style={{ padding: "12px var(--gutter)" }}>
        <CapsuleNav />
      </header>
      <main id="main">
        <Hero />
      </main>
    </>
  );
}
