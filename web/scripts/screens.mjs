// Playwright screenshot set (design/screens/). Usage: node scripts/screens.mjs <baseUrl> [prefix]
// Captures each page in each effects tier and records page FPS where the page reports it.
import { chromium } from "playwright";
import fs from "node:fs";

const base = process.argv[2] || "http://127.0.0.1:8000";
const prefix = process.argv[3] || "";
const pages = (process.env.PAGES || "/,/lab/").split(",");
const tiers = (process.env.TIERS || "full,lite,off").split(",");
const out = new URL("../../design/screens/", import.meta.url).pathname;
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--enable-unsafe-swiftshader"] });
const results = [];
for (const vp of [{ name: "desktop", width: 1440, height: 900 }, { name: "phone", width: 390, height: 844 }]) {
  for (const tier of tiers) {
    for (const p of pages) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1,
        reducedMotion: tier === "reduced" ? "reduce" : "no-preference" });
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(`${base}${p}?effects=${tier === "reduced" ? "auto" : tier}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(3500);
      const name = `${prefix}${p.replace(/\//g, "_").replace(/^_|_$/g, "") || "landing"}-${tier}-${vp.name}.png`;
      await page.screenshot({ path: out + name });
      const fps = await page.locator("[data-testid=fps]").first().textContent({ timeout: 500 }).catch(() => null);
      results.push({ page: p, tier, viewport: vp.name, file: name, fps, errors });
      await ctx.close();
    }
  }
}
await browser.close();
console.log(JSON.stringify(results, null, 1));
