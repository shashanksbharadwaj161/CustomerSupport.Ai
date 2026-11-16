// Silent walkthrough video of the demo flow (Playwright screen recording, NO audio).
// Usage: node scripts/record_demo.mjs <baseUrl> <fakeMicWav> [outDir]
// The real fallback video for a client must be recorded with audio (e.g. OBS) on the demo machine.
import { chromium } from "playwright";
const [base = "http://127.0.0.1:8000", wav, outDir = "../data/demo-video"] = process.argv.slice(2);
const b = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
  ...(wav ? [`--use-file-for-fake-audio-capture=${wav}`] : []), "--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader"] });
const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: outDir, size: { width: 1280, height: 720 } }, permissions: ["microphone"] });
const p = await ctx.newPage();
const pause = (ms) => p.waitForTimeout(ms);
await p.goto(`${base}/?effects=lite`, { waitUntil: "networkidle" }); await pause(4000);
for (const f of [1.2, 2, 3, 4, 5, 6.5]) { await p.evaluate((f) => window.scrollTo({ top: innerHeight * f, behavior: "smooth" }), f); await pause(1500); }
await p.goto(`${base}/studio/?id=lotus-bank&effects=lite`, { waitUntil: "networkidle" }); await pause(1500);
for (const t of ["Persona", "Guardrails", "Languages", "Versions"]) { await p.getByRole("tab", { name: t }).click(); await pause(1400); }
await p.goto(`${base}/knowledge/?effects=lite`, { waitUntil: "networkidle" }); await pause(1000);
await p.locator("aside button").first().click().catch(() => {}); await pause(2500);
await p.goto(`${base}/call/?effects=lite&transport=websocket&profile=lotus-bank`, { waitUntil: "networkidle" }); await pause(1000);
await p.click("[data-testid=start-call]");
await p.waitForFunction(() => (window.__shaon?.turns?.length ?? 0) >= 1, null, { timeout: 180000 }).catch(() => {});
await pause(6000);
await p.click("[data-testid=end-call]").catch(() => {});
await p.goto(`${base}/logs/?effects=lite`, { waitUntil: "networkidle" }); await pause(1500);
await p.locator("text=open").first().click().catch(() => {}); await pause(1500);
await p.click("[data-testid=replay]").catch(() => {}); await pause(6000);
const path = await p.video().path();
await ctx.close(); await b.close();
console.log("video:", path);
