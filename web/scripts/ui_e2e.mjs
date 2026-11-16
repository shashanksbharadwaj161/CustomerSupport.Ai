// UI E2E checks per page (no audio). Usage: node scripts/ui_e2e.mjs <baseUrl> [suite...]
import { chromium } from "playwright";
const base = process.argv[2] || "http://127.0.0.1:8000";
const suites = process.argv.slice(3);
const browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader"] });
const results = {};
async function run(name, fn) {
  if (suites.length && !suites.includes(name)) return;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  try { await fn(page); results[name] = errors.length ? { ok: false, errors } : { ok: true }; }
  catch (e) { results[name] = { ok: false, error: String(e).slice(0, 400), errors }; }
  await ctx.close();
}

await run("studio", async (page) => {
  await page.goto(`${base}/studio/?id=lotus-bank&effects=off`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-testid=agent-name]");
  const before = await page.locator("[data-testid=save-profile]").textContent();
  await page.fill("[data-testid=agent-name]", "Lotus Bay Bank support (edited)");
  await page.click("[data-testid=save-profile]");
  await page.waitForSelector("text=Saved as version", { timeout: 10000 });
  await page.getByRole("tab", { name: "Versions" }).click();
  await page.waitForSelector("[data-testid=versions] >> text=Roll back to v1");
  await page.click("text=Roll back to v1");
  await page.waitForSelector("text=Rolled back", { timeout: 10000 });
  const name = await page.inputValue("[data-testid=agent-name]").catch(() => null);
  for (const t of ["Persona", "Guardrails", "Languages", "Voices", "Knowledge", "Tools"]) {
    await page.getByRole("tab", { name: t }).click();
    await page.waitForSelector(`[data-testid=tab-${t}]`);
  }
  const after = await page.locator("[data-testid=save-profile]").textContent();
  const n = (s) => Number(String(s).match(/\d+/)?.[0]);
  if (n(after) !== n(before) + 2) throw new Error(`versions did not advance: ${before} -> ${after}`); // save + rollback
});

await run("settings", async (page) => {
  await page.goto(`${base}/settings/?effects=off`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-testid=key-status]");
  await page.waitForSelector("[data-testid=engines-table]");
  await page.fill("[data-testid=cap-input]", "7.5");
  await page.click("text=Save cap");
  await page.waitForSelector("text=Spend cap saved");
  const spent = await page.textContent("[data-testid=spent]");
  if (!spent.includes("7.50")) throw new Error("cap not shown: " + spent);
});

await run("voices", async (page) => {
  await page.goto(`${base}/settings/?effects=off`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-testid=voice-kokoro_en_heart]");
  await page.click("[data-testid=preview-kokoro_en_heart]");
  await page.waitForSelector("[data-testid=voices-msg]", { timeout: 120000 });
  const m = await page.textContent("[data-testid=voices-msg]");
  if (!/s preview/.test(m)) throw new Error("preview failed: " + m);
  await page.getByRole("tab", { name: "ಕನ್ನಡ" }).click();
  await page.click("[data-testid=preview-parler_kn_anu]");
  await page.waitForFunction(() => /PENDING|preview/.test(document.querySelector("[data-testid=voices-msg]")?.textContent || ""), null, { timeout: 60000 });
});

for (const mode of ["sse", "poll"]) {
  await run(`knowledge-${mode}`, async (page) => {
    await page.goto(`${base}/knowledge/?effects=off${mode === "poll" ? "&poll=1" : ""}`, { waitUntil: "networkidle" });
    await page.fill("[data-testid=kb-url]", `${base}/demo-sites/lotus-bank/`);
    await page.check("[data-testid=kb-perm]");
    await page.click("[data-testid=kb-start]");
    await page.waitForFunction(() => /ready|error/.test(document.querySelector("[data-testid=kb-status]")?.textContent || ""), null, { timeout: 120000 });
    const status = await page.textContent("[data-testid=kb-status]");
    if (!status.startsWith("ready")) throw new Error(status);
    const nodes = await page.locator("[data-testid=crawl-graph] g.node").count();
    if (nodes < 5) throw new Error(`only ${nodes} page nodes`);
    await page.fill("[data-testid=kb-question]", "What are the branch opening hours on Saturday?");
    await page.click("[data-testid=kb-ask]");
    await page.waitForSelector("[data-testid=kb-answer]", { timeout: 60000 });
    const txt = await page.textContent("[data-testid=kb-answer]");
    if (!/Saturday/.test(txt)) throw new Error("answer passages missing hours: " + txt.slice(0, 200));
    const log = await page.textContent("details:has-text('Event log')");
    if (/private\/internal/.test(log) && !/robots/.test(log)) throw new Error("private page crawled");
  });
}

await browser.close();
console.log(JSON.stringify(results, null, 1));
process.exit(Object.values(results).every((r) => r.ok) ? 0 : 1);
