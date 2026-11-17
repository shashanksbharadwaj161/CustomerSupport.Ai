// Two-speaker website recording (tests/e2e/conversations/record_conversations.py drives this).
// A HEADED Chromium shows the real /call/ page on an X display; its microphone is the PulseAudio "customer" sink
// monitor, its speaker output goes to the "callmix" sink. One ffmpeg process records the screen (x11grab) and the
// callmix monitor (agent playback + customer voice, via a loopback) together, so picture and both voices share one
// clock. The CUSTOMER is this script: after the agent has finished speaking it plays the next pre-synthesised customer
// line into the customer sink (paplay). Nothing is edited afterwards.
// Usage: node scripts/conversation_record.mjs <baseUrl> <lang> <out.mp4> <result.json> <wav1> <wav2> ...
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";

const [base, lang, outMp4, outJson, ...wavs] = process.argv.slice(2);
const display = process.env.DISPLAY || ":99";
const W = 1280, H = 720;
const t0 = Date.now();
const log = [];
const mark = (ev, extra = {}) => { const e = { t: (Date.now() - t0) / 1000, ev, ...extra }; log.push(e); console.error(JSON.stringify(e)); };

const browser = await chromium.launch({
  headless: false,
  // no window manager on the X display: --kiosk is ignored, so the window is made taller by the toolbar height and
  // ffmpeg records exactly the 1280x720 page area below it (measured, not guessed)
  args: ["--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required", `--window-size=${W},${H + 88}`,
    "--window-position=0,0", "--enable-unsafe-swiftshader", "--disable-features=Translate", "--hide-scrollbars"],
});
const ctx = await browser.newContext({ viewport: null, permissions: ["microphone"] });
const page = await ctx.newPage();
page.on("pageerror", (e) => mark("pageerror", { e: String(e).slice(0, 200) }));
await page.goto(`${base}/call/?transport=websocket&effects=lite&profile=lotus-bank`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("[data-testid=start-call]:not([disabled])", { timeout: 60000 });
await page.waitForTimeout(2500);
const geo = await page.evaluate(() => ({ iw: innerWidth, ih: innerHeight, ow: outerWidth, oh: outerHeight }));
const top = Math.max(0, geo.oh - geo.ih);
mark("geometry", { ...geo, top });
if (geo.ih < H) throw new Error(`viewport ${geo.iw}x${geo.ih} smaller than ${W}x${H}`);

// recorder: screen + mixed audio in one process (shared wall clock)
const ff = spawn("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y",
  "-thread_queue_size", "1024", "-f", "x11grab", "-video_size", `${W}x${H}`, "-framerate", "25", "-draw_mouse", "0", "-i", `${display}.0+0,${top}`,
  "-thread_queue_size", "1024", "-f", "pulse", "-i", "callmix.monitor",
  "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p",
  "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", outMp4], { stdio: ["pipe", "inherit", "inherit"] });
await new Promise((r) => setTimeout(r, 1200));
mark("record_start");

const msgs = () => page.evaluate(() => (window.__shaon?.messages || []).map((m) => ({ event: m.event, role: m.role, text: m.text, lang: m.lang,
  greeting: !!m.greeting, state: m.state, first_audio_ms: m.first_audio_ms, voice: m.voice, engine: m.engine, gen_ms: m.gen_ms,
  stt_ms: m.stt_ms, model: m.model, model_served: m.model_served, reason: m.reason, detail: m.detail, stage: m.stage,
  engines: m.engines, fallbacks: m.fallbacks, demo_only: m.demo_only, audio_s: m.audio_s, at: m.__t })));
const agentLines = async () => (await msgs()).filter((m) => m.event === "transcript" && m.role === "agent").length;

/** Wait until the agent has produced `n` agent lines AND has gone through `n` complete speaking cycles (state
 *  "speaking" seen and ended) and stays quiet for `quietMs`. A text line alone is not enough: the audio of a sentence
 *  starts seconds after its text (synthesis), and the customer must not talk over it. */
async function waitAgentDone(n, timeoutMs = 120000, quietMs = 1600) {
  const start = Date.now();
  let quietSince = null;
  while (Date.now() - start < timeoutMs) {
    const ms = await msgs();
    const lines = ms.filter((m) => m.event === "transcript" && m.role === "agent").length;
    const spoke = ms.filter((m) => m.event === "state" && m.state === "speaking").length;
    const st = await page.getAttribute("[data-testid=call-stage]", "data-state").catch(() => null);
    if (lines >= n && spoke >= n && st !== "speaking" && st !== "thinking") {
      quietSince ??= Date.now();
      if (Date.now() - quietSince >= quietMs) return true;
    } else quietSince = null;
    await page.waitForTimeout(150);
  }
  return false;
}

await page.click("[data-testid=start-call]");
mark("call_start");
const okGreeting = await waitAgentDone(1);
mark("greeting_done", { ok: okGreeting });

for (const [i, wav] of wavs.entries()) {
  await page.waitForTimeout(500);
  mark("customer_start", { turn: i + 1 });
  await new Promise((res, rej) => { const p = spawn("paplay", ["--device=customer", wav]); p.on("exit", (c) => (c === 0 ? res() : rej(new Error(`paplay ${c}`)))); });
  mark("customer_end", { turn: i + 1 });
  const ok = await waitAgentDone(2 + i);
  mark("agent_done", { turn: i + 1, ok });
}
await page.waitForTimeout(800);
await page.click("[data-testid=end-call]").catch(() => {});
await page.waitForTimeout(700);
mark("call_end");
ff.stdin.write("q");
await new Promise((r) => ff.on("exit", r));
mark("record_end");

const data = await page.evaluate(() => window.__shaon || {});
fs.writeFileSync(outJson, JSON.stringify({ lang, log, messages: await msgs(), turns: data.turns || [] }, null, 1));
await browser.close();
