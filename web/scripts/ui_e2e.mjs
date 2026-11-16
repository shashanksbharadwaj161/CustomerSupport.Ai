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

await browser.close();
console.log(JSON.stringify(results, null, 1));
process.exit(Object.values(results).every((r) => r.ok) ? 0 : 1);
