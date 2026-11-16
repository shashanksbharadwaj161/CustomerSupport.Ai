"""Website crawler for the knowledge base (PLAN.md section 8, CLAUDE.md ingestion rules).

- Only sites the user owns or has permission for (the UI says so; when exposed, an allowlist is enforced).
- Our own robots.txt check with our clear user agent (urllib.robotparser), before every page.
- Same host AND under the start URL's path; depth and page limits; no query-string explosions.
- Fetch with httpx; render JavaScript with Crawl4AI (headless Chromium) when a page needs it,
  falling back to Playwright directly if Crawl4AI is not installed.
"""
from __future__ import annotations

import asyncio
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

USER_AGENT = "ShaOnVoiceAI-KnowledgeBot/0.1 (+demo crawler; only sites the operator owns or may crawl)"
Event = Callable[[str, dict], Awaitable[None]]


@dataclass
class Limits:
    max_depth: int = 3
    max_pages: int = 50
    render_js: str = "auto"  # auto | always | never
    timeout_s: float = 15.0
    delay_s: float = 0.2


@dataclass
class Page:
    url: str
    html: str
    depth: int
    rendered: bool
    status: int
    links: list[str] = field(default_factory=list)


class CrawlNotAllowed(Exception):
    pass


def same_scope(url: str, start: str) -> bool:
    u, s = urlparse(url), urlparse(start)
    if (u.scheme, u.netloc) != (s.scheme, s.netloc):
        return False
    base = s.path if s.path.endswith("/") else s.path.rsplit("/", 1)[0] + "/"
    return u.path.startswith(base) or u.path == s.path


def normalize(url: str) -> str:
    url, _ = urldefrag(url)
    p = urlparse(url)
    if p.query:  # ignore query strings (calendars, filters) to avoid crawl explosions
        url = url.split("?", 1)[0]
    return url


def extract_links(html: str, base: str) -> list[str]:
    out = []
    for m in re.finditer(r"""href\s*=\s*["']([^"'#]+)""", html, re.I):
        href = m.group(1).strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        out.append(normalize(urljoin(base, href)))
    return out


def needs_render(html: str) -> bool:
    """Heuristic: little visible text, or a JS app shell."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    text = " ".join(soup.get_text(" ").split())
    return len(text) < 200 or bool(re.search(r'<div id="(root|app|__next)"></div>', html))


class Renderer:
    """Headless-Chromium rendering. Crawl4AI if installed (PLAN), else Playwright."""

    name = "none"

    def __init__(self):
        self._crawler = None
        self._pw = None
        self._browser = None
        try:
            import crawl4ai  # noqa: F401
            self.name = "crawl4ai"
        except ImportError:
            try:
                import playwright  # noqa: F401
                self.name = "playwright"
            except ImportError:
                self.name = "none"

    async def render(self, url: str, timeout_s: float) -> str:
        if self.name == "crawl4ai":
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            if self._crawler is None:
                self._crawler = AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False, user_agent=USER_AGENT))
                await self._crawler.start()
            r = await self._crawler.arun(url, config=CrawlerRunConfig(verbose=False, page_timeout=int(timeout_s * 1000)))
            if not r.success:
                raise RuntimeError(r.error_message or "render failed")
            return r.html or ""
        if self.name == "playwright":
            from playwright.async_api import async_playwright

            if self._browser is None:
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch()
            page = await self._browser.new_page(user_agent=USER_AGENT)
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_s * 1000)
                return await page.content()
            finally:
                await page.close()
        raise RuntimeError("no JS renderer installed (pip install crawl4ai or playwright)")

    async def close(self):
        try:
            if self._crawler:
                await self._crawler.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass


async def crawl(start_url: str, limits: Limits, emit: Event, allowlist: list[str] | None = None,
                renderer: Renderer | None = None) -> list[Page]:
    start_url = normalize(start_url)
    host = (urlparse(start_url).hostname or "").lower()
    if urlparse(start_url).scheme not in ("http", "https"):
        raise CrawlNotAllowed("only http(s) URLs")
    if allowlist is not None and not any(host == d or host.endswith("." + d) for d in allowlist):
        raise CrawlNotAllowed(f"{host} is not on the crawl allowlist (CRAWL_ALLOWLIST)")

    renderer = renderer or Renderer()
    pages: list[Page] = []
    seen = {start_url}
    queue: list[tuple[str, int]] = [(start_url, 0)]
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                                 timeout=limits.timeout_s) as client:
        robots = urllib.robotparser.RobotFileParser()
        robots_url = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}/robots.txt"
        try:
            r = await client.get(robots_url)
            robots.parse(r.text.splitlines() if r.status_code == 200 else [])
            await emit("robots", {"url": robots_url, "status": r.status_code})
        except httpx.HTTPError as e:
            robots.parse([])
            await emit("robots", {"url": robots_url, "status": None, "error": str(e)[:120]})

        try:
            while queue and len(pages) < limits.max_pages:
                url, depth = queue.pop(0)
                if not robots.can_fetch(USER_AGENT, url):
                    await emit("skipped", {"url": url, "reason": "robots.txt disallows"})
                    continue
                try:
                    resp = await client.get(url)
                except httpx.HTTPError as e:
                    await emit("skipped", {"url": url, "reason": f"fetch error {type(e).__name__}"})
                    continue
                ctype = resp.headers.get("content-type", "")
                if resp.status_code != 200 or "html" not in ctype:
                    await emit("skipped", {"url": url, "reason": f"HTTP {resp.status_code} {ctype.split(';')[0]}"})
                    continue
                html, rendered = resp.text, False
                if limits.render_js == "always" or (limits.render_js == "auto" and needs_render(html)):
                    try:
                        html = await renderer.render(url, limits.timeout_s)
                        rendered = True
                    except Exception as e:
                        await emit("warning", {"url": url, "reason": f"JS render failed: {str(e)[:120]}"})
                links = [l for l in extract_links(html, str(resp.url)) if same_scope(l, start_url)]
                pages.append(Page(url=str(resp.url), html=html, depth=depth, rendered=rendered, status=resp.status_code, links=links))
                await emit("page", {"url": str(resp.url), "depth": depth, "rendered": rendered, "n": len(pages)})
                if depth < limits.max_depth:
                    for l in links:
                        if l not in seen:
                            seen.add(l)
                            queue.append((l, depth + 1))
                await asyncio.sleep(limits.delay_s)
        finally:
            await renderer.close()
    return pages
