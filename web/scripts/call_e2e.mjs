// Browser E2E: Chromium with a fake microphone (Kokoro-generated WAV) talks to the real pipeline.
// Usage: node tests/e2e/call_e2e.mjs <baseUrl> <wav> <transport> <effects> <expectUserRegex> <expectAgentRegex> [profile]
// Prints JSON: transcripts, server first_audio_ms, client first-audio ms, tier. Exit 1 on failure.
import { chromium } from "playwright";

const [base, wav, transport, effects, userRe, agentRe, profile] = process.argv.slice(2);
const browser = await chromium.launch({ args: [
  "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${wav}`,
  "--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader"] });
const ctx = await browser.newContext({ permissions: ["microphone"], viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const q = new URLSearchParams({ transport, effects, ...(profile ? { profile } : {}) });
await page.goto(`${base}/call/?${q}`, { waitUntil: "networkidle" });
await page.waitForSelector("[data-testid=start-call]:not([disabled])", { timeout: 20000 });
const t0 = Date.now();
await page.click("[data-testid=start-call]");
let result = null;
try {
  const want = Number(process.env.WAIT_TURNS || 1);
  await page.waitForFunction((n) => (window.__shaon?.turns?.length ?? 0) >= n &&
    window.__shaon.messages.filter((m) => m.event === "transcript" && m.role === "agent" && !m.greeting).length >= n, want, { timeout: 240000, polling: 500 });
} catch (e) { errors.push("timeout waiting for first turn"); }
const data = await page.evaluate(() => window.__shaon);
const user = data.messages.filter((m) => m.event === "transcript" && m.role === "user").map((m) => ({ text: m.text, lang: m.lang, reason: m.reason, stt_ms: m.stt_ms }));
const agent = data.messages.filter((m) => m.event === "transcript" && m.role === "agent").map((m) => ({ text: m.text, lang: m.lang, greeting: !!m.greeting }));
const tts = data.messages.filter((m) => m.event === "tts").map((m) => ({ lang: m.lang, voice: m.voice, gen_ms: m.gen_ms }));
const meta = data.messages.filter((m) => m.event === "turn_meta");
result = { transport, effects, wall_s: (Date.now() - t0) / 1000, user, agent, tts, turns: data.turns, meta, errors };
const shot = process.env.SHOT;
if (shot) await page.screenshot({ path: shot });
await page.click("[data-testid=end-call]").catch(() => {});
await browser.close();
const ok = errors.length === 0 && user.some((u) => new RegExp(userRe, "i").test(u.text)) &&
  agent.some((a) => !a.greeting && new RegExp(agentRe, "i").test(a.text)) && data.turns.length >= 1;
console.log(JSON.stringify({ ok, ...result }, null, 1));
process.exit(ok ? 0 : 1);
