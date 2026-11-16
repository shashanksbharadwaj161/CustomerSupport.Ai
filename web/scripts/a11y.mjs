// axe-core WCAG 2.0/2.1 A + AA scan of every page. Usage: node scripts/a11y.mjs <baseUrl>
import { chromium } from "playwright";
import fs from "node:fs";
const base = process.argv[2] || "http://127.0.0.1:8000";
const axe = fs.readFileSync(new URL("../node_modules/axe-core/axe.min.js", import.meta.url), "utf8");
const pages = ["/", "/studio/", "/call/", "/knowledge/", "/logs/", "/settings/", "/lab/"];
const b = await chromium.launch({ args: ["--enable-unsafe-swiftshader"] });
const report = {};
for (const p of pages) {
  const page = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`${base}${p}?effects=off`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.addScriptTag({ content: axe });
  const r = await page.evaluate(async () => (await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] })).violations
    .map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, sample: v.nodes.slice(0, 2).map((n) => n.target.join(" ") + " :: " + (n.failureSummary || "").split("\n")[1]) })));
  report[p] = r;
  await page.close();
}
await b.close();
console.log(JSON.stringify(report, null, 1));
process.exit(Object.values(report).every((v) => v.length === 0) ? 0 : 1);
