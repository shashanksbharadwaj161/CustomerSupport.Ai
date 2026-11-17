// Visitor-facing share-mode checks. Usage: node scripts/share_ui_e2e.mjs <base> <passcode> <fakeMicWav>
// Prints one JSON line per check; prints "KILL_SERVER" when the orchestrator should kill the app (offline test).
import { chromium } from "playwright";
import path from "node:path";
import readline from "node:readline";
const [base, pass, wavArg] = process.argv.slice(2);
const wav = path.resolve(wavArg);
const b = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
  `--use-file-for-fake-audio-capture=${wav}`, "--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader"] });
const out = (name, ok, extra = {}) => console.log(JSON.stringify({ check: name, ok, ...extra }));
async function visitor(code = pass) {
  const ctx = await b.newContext({ permissions: ["microphone"], viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`${base}/call/?transport=websocket&effects=off`, { waitUntil: "networkidle" });
  await p.fill("[data-testid=passcode]", code); await p.click("[data-testid=passcode-submit]");
  return p;
}
try {
  const w = await visitor("definitely-wrong");
  const err = await w.waitForSelector("[data-testid=passcode-error]", { timeout: 10000 }).then((e) => e.textContent()).catch(() => null);
  out("wrong_passcode_rejected", !!err && /did not work/.test(err), { message: err });
  await w.context().close();

  const a = await visitor();
  await a.waitForSelector("[data-testid=get-ready]", { timeout: 15000 });
  const ws = await a.waitForFunction(() => /works/.test(document.querySelector("[data-testid=ws-status]")?.textContent || ""), null, { timeout: 15000 }).then(() => true).catch(() => false);
  const badges = await a.locator("[data-testid=lang-readiness] li").count();
  out("get_ready_ws_and_languages", ws && badges === 5, { badges });

  await a.click("[data-testid=start-call]");
  await a.waitForFunction(() => window.__shaon?.messages?.some((m) => m.event === "hello"), null, { timeout: 60000 });
  const t0 = Date.now();
  const bp = await visitor();
  await bp.waitForSelector("[data-testid=start-call]:not([disabled])", { timeout: 15000 });
  await bp.click("[data-testid=start-call]");
  const busy = await bp.waitForSelector("[data-testid=screen-busy]", { timeout: 20000 }).then(() => true).catch(() => false);
  out("second_caller_sees_busy", busy);
  await bp.context().close();

  const ended = await a.waitForSelector("[data-testid=screen-ended]", { timeout: 60000 }).then((e) => e.textContent()).catch(() => null);
  out("max_call_length_ends_call", !!ended && /20 seconds/.test(ended) && !/0 minutes/.test(ended), { after_s: Math.round((Date.now() - t0) / 1000), text: ended?.slice(0, 120) });
  await a.context().close();

  const c = await visitor();
  await c.waitForSelector("[data-testid=start-call]:not([disabled])", { timeout: 15000 });
  await c.click("[data-testid=start-call]");
  await c.waitForFunction(() => window.__shaon?.messages?.some((m) => m.event === "hello"), null, { timeout: 60000 });
  console.log("KILL_SERVER");
  const lost = await c.waitForSelector("[data-testid=screen-lost]", { timeout: 40000 }).then((e) => e.textContent()).catch(() => null);
  const blank = await c.evaluate(() => document.body.innerText.trim().length < 20);
  out("offline_mid_call_shows_friendly_state", !!lost && !blank, { text: lost?.slice(0, 140) });
} finally { await b.close(); }
