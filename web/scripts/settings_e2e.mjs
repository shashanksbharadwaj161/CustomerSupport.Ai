// Settings UI E2E on a LOCAL PREVIEW server (no passcode). Uses a FAKE key and never presses "Test key" or starts a
// call, so no Anthropic request is made. Checks: every page opens without a login, key save -> masked status, model
// pick -> persists after reload and shows in the status strip, cap edit, the fake key never appears in any response.
// Usage: node scripts/settings_e2e.mjs <baseUrl> <fakeKey>
import { chromium } from "playwright";

const [base, fakeKey] = process.argv.slice(2);
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok: !!ok, detail: String(detail).slice(0, 200) }); };
const browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const leaks = [];
page.on("response", async (r) => {
  try { const b = await r.text(); if (b.includes(fakeKey)) leaks.push(r.url()); } catch {}
});

// 1. no login anywhere
for (const p of ["/", "/call/", "/studio/", "/knowledge/", "/logs/", "/settings/"]) {
  await page.goto(`${base}${p}?effects=off`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  const gate = await page.locator("[data-testid=passcode]").count();
  check(`open ${p} without passcode`, gate === 0 && (await page.locator("main#main").count()) === 1);
}

// 2. save a (fake) key: masked, never echoed
await page.goto(`${base}/settings/?effects=off`, { waitUntil: "networkidle" });
await page.fill("[data-testid=key-input]", fakeKey);
await page.click("[data-testid=save-key]");
await page.waitForSelector("text=Key saved", { timeout: 10000 });
const status = await page.textContent("[data-testid=key-status]");
check("key status masked (last 4 only)", status.includes(fakeKey.slice(-4)) && !status.includes(fakeKey), status);
check("key input cleared after save", (await page.inputValue("[data-testid=key-input]")) === "");
check("answering shows a Claude model", /claude-/.test(status), status);

// 3. pick a model, save, reload: persisted, active, shown in status strip
await page.click("[data-testid=model-claude-sonnet-5-5]");
await page.selectOption("[data-testid=fallback-select]", "claude-haiku-5-5");
await page.click("[data-testid=save-model]");
await page.waitForSelector("[data-testid=model-msg] >> text=New calls use claude-sonnet-5-5", { timeout: 10000 });
await page.reload({ waitUntil: "networkidle" });
const active = await page.textContent("[data-testid=active-model]");
check("model persisted after reload", active.includes("claude-sonnet-5-5"), active);
await page.waitForFunction(() => /claude-sonnet-5-5/.test(document.querySelector("[data-testid=status-llm]")?.textContent || ""), null, { timeout: 20000 }).catch(() => {});
check("status strip shows the active model", /claude-sonnet-5-5/.test(await page.textContent("[data-testid=status-llm]")));

// 4. unlisted model needs the explicit tick
await page.fill("[data-testid=custom-model]", "claude-made-up-9");
check("unlisted ID cannot be saved without the tick", await page.isDisabled("[data-testid=save-model]"));
await page.fill("[data-testid=custom-model]", "");

// 5. spend cap
await page.fill("[data-testid=cap-input]", "12.5");
await page.click("text=Save cap");
await page.waitForSelector("text=Spend cap saved", { timeout: 10000 });
check("cap saved", (await page.textContent("[data-testid=spent]")).includes("12.50"));

// 6. orb interaction states (landing demo): state buttons change the stage, keyboard rotates
await page.goto(`${base}/?effects=lite`, { waitUntil: "networkidle" });
await page.click("[data-testid=demo-controls] >> text=Think");
check("demo: thinking state", (await page.getAttribute("[data-testid=hero-stage]", "data-state")) === "thinking");
await page.click("[data-testid=demo-controls] >> text=Speak");
check("demo: speaking state", (await page.getAttribute("[data-testid=hero-stage]", "data-state")) === "speaking");
await page.focus("[data-testid=hero-stage]");
await page.keyboard.press("ArrowRight");
check("demo labelled simulated", (await page.locator("[data-testid=hero-stage] >> text=Simulated demo").count()) === 1);

check("fake key never in any HTTP response", leaks.length === 0, leaks.join(" "));
await browser.close();
for (const r of results) console.log(`${r.name.padEnd(48)} ${r.ok ? "PASS" : "FAIL"} ${r.ok ? "" : r.detail}`);
process.exit(results.every((r) => r.ok) ? 0 : 1);
