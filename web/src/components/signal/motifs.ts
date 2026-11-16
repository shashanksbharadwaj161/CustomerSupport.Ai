/**
 * Particle target shapes ("glyph motifs") per language, plus a text motif sampled from a
 * canvas (Latin letters only: the ASCII/particle layer never renders Indic or Japanese
 * script, DESIGN.md section 5). All deterministic per particle index.
 */
import type { Lang } from "@/lib/tokens";

export type Motif = Lang | "word" | "sphere";

function rand(i: number, k: number) {
  const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

export function motifPositions(motif: Motif, n: number, word = "SHAON"): Float32Array {
  const out = new Float32Array(n * 3);
  if (motif === "word") return wordPositions(word, n, out);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    let x = 0, y = 0, z = 0;
    const t = i / n, r1 = rand(i, 1), r2 = rand(i, 2);
    switch (motif) {
      case "en":
      case "sphere": { // fibonacci sphere
        const yy = 1 - (i / (n - 1)) * 2, rad = Math.sqrt(1 - yy * yy), th = golden * i;
        x = Math.cos(th) * rad; y = yy; z = Math.sin(th) * rad; break;
      }
      case "ja": { // enso: thick ring with a brush-like gap
        const a = t * Math.PI * 1.88 + 0.3, R = 0.95, w = 0.08 + 0.12 * Math.sin(t * Math.PI);
        x = Math.cos(a) * (R + (r1 - 0.5) * w); y = Math.sin(a) * (R + (r1 - 0.5) * w); z = (r2 - 0.5) * w; break;
      }
      case "hi": { // two interlocked rings
        const a = t * Math.PI * 4, ring = i % 2, R = 0.78;
        const cx = ring ? 0.32 : -0.32;
        x = cx + Math.cos(a) * R * 0.75; y = Math.sin(a) * R * (ring ? 1 : 0.92);
        z = ring ? Math.sin(a) * 0.25 : -Math.sin(a) * 0.25; x += (r1 - 0.5) * 0.05; y += (r2 - 0.5) * 0.05; break;
      }
      case "bn": { // flowing wave disc
        const a = golden * i, r = Math.sqrt(t);
        x = Math.cos(a) * r; z = Math.sin(a) * r * 0.6; y = Math.sin(x * 5) * 0.18 + Math.cos(z * 6) * 0.12; break;
      }
      case "kn": { // double helix spiral
        const a = t * Math.PI * 10, strand = i % 2 ? Math.PI : 0;
        y = (t - 0.5) * 2; x = Math.cos(a + strand) * 0.55; z = Math.sin(a + strand) * 0.55;
        x += (r1 - 0.5) * 0.06; z += (r2 - 0.5) * 0.06; break;
      }
    }
    out[i * 3] = x; out[i * 3 + 1] = y; out[i * 3 + 2] = z;
  }
  return out;
}

function wordPositions(word: string, n: number, out: Float32Array): Float32Array {
  if (typeof document === "undefined") return motifPositions("sphere", n);
  const c = document.createElement("canvas");
  const W = 600, H = 160;
  c.width = W; c.height = H;
  const g = c.getContext("2d");
  if (!g) return motifPositions("sphere", n);
  g.fillStyle = "#000"; g.fillRect(0, 0, W, H);
  g.fillStyle = "#fff"; g.font = "800 140px 'Space Grotesk', sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(word, W / 2, H / 2 + 6);
  const data = g.getImageData(0, 0, W, H).data;
  const pts: number[] = [];
  for (let y = 0; y < H; y += 2) for (let x = 0; x < W; x += 2) if (data[(y * W + x) * 4] > 128) pts.push(x, y);
  const m = pts.length / 2 || 1;
  for (let i = 0; i < n; i++) {
    const k = Math.floor(rand(i, 3) * m);
    out[i * 3] = ((pts[k * 2] ?? W / 2) / W - 0.5) * 3.2;
    out[i * 3 + 1] = -((pts[k * 2 + 1] ?? H / 2) / H - 0.5) * 0.85 + 0.55; // sits above the hero headline
    out[i * 3 + 2] = (rand(i, 4) - 0.5) * 0.12;
  }
  return out;
}
