/**
 * JS access to design tokens. Values are READ from tokens.css (the single source),
 * never hard-coded here, so GSAP / three.js use the same palette and timings as CSS.
 */
export type Lang = "en" | "ja" | "hi" | "bn" | "kn";
export const LANGS: Lang[] = ["en", "ja", "hi", "bn", "kn"];

/** Display names: Latin names for the ASCII/mono layer, native names for DOM text. */
export const LANG_NAMES: Record<Lang, { latin: string; native: string }> = {
  en: { latin: "ENGLISH", native: "English" },
  ja: { latin: "NIHONGO", native: "日本語" },
  hi: { latin: "HINDI", native: "हिन्दी" },
  bn: { latin: "BANGLA", native: "বাংলা" },
  kn: { latin: "KANNADA", native: "ಕನ್ನಡ" },
};

function css(name: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export const token = {
  color: (name: string) => css(`--${name}`),
  langColor: (lang: Lang) => css(`--lang-${lang}`),
  /** duration in seconds (GSAP) */
  dur: (name: "fast" | "base" | "slow") => parseFloat(css(`--dur-${name}`) || "0") / 1000,
  /** cubic-bezier control points for CustomEase */
  ease: (name: "enter" | "exit" | "emphasis") => {
    const m = css(`--ease-${name}`).match(/cubic-bezier\(([^)]+)\)/);
    return m ? m[1].split(",").map((s) => parseFloat(s)) : [0.25, 0.1, 0.25, 1];
  },
  num: (name: string, fallback = 0) => {
    const v = parseFloat(css(`--${name}`));
    return Number.isFinite(v) ? v : fallback;
  },
};

/** SVG-path form of a token easing for gsap CustomEase.create(name, path). */
export function easePath(name: "enter" | "exit" | "emphasis"): string {
  const [x1, y1, x2, y2] = token.ease(name);
  return `M0,0 C${x1},${y1} ${x2},${y2} 1,1`;
}

/** "20 seconds" / "5 minutes": human duration for limits shown to visitors. */
export function humanDuration(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} seconds`;
  const m = Math.round(seconds / 60);
  return `${m} minute${m === 1 ? "" : "s"}`;
}
