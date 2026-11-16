"""HTML -> clean markdown-ish text, cross-page boilerplate removal, heading-based chunks."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass

from bs4 import BeautifulSoup

DROP = ["script", "style", "noscript", "template", "nav", "header", "footer", "aside", "form", "svg", "iframe"]


@dataclass
class CleanPage:
    url: str
    title: str
    text: str  # lines; headings prefixed with '#'
    lang: str | None = None


def html_to_text(html: str, url: str) -> CleanPage:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(" ").strip() if soup.title else "") or url
    lang = soup.html.get("lang") if soup.html else None
    for t in soup(DROP):
        t.decompose()
    lines = []
    body = soup.body or soup
    for el in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "dt", "dd", "blockquote", "pre"]):
        if el.find(["p", "li", "h1", "h2", "h3"]):  # skip containers; their children are visited
            continue
        txt = " ".join(el.get_text(" ").split())
        if not txt:
            continue
        lines.append(("#" * int(el.name[1]) + " " + txt) if el.name in ("h1", "h2", "h3", "h4") else txt)
    if not lines:  # pages without semantic tags
        lines = [" ".join(x.split()) for x in body.get_text("\n").split("\n") if x.strip()]
    return CleanPage(url=url, title=title, text="\n".join(lines), lang=lang)


def dedupe(pages: list[CleanPage], min_pages: int = 3, share: float = 0.5) -> tuple[list[CleanPage], int]:
    """Drop exact-duplicate pages and lines that repeat on more than `share` of pages (menus, footers)."""
    out, hashes = [], set()
    for p in pages:
        h = hashlib.sha256(p.text.encode()).hexdigest()
        if h not in hashes and p.text.strip():
            hashes.add(h)
            out.append(p)
    removed = 0
    if len(out) >= min_pages:
        counts = Counter(l for p in out for l in set(p.text.splitlines()))
        boiler = {l for l, c in counts.items() if c / len(out) > share and not l.startswith("#")}
        for p in out:
            kept = [l for l in p.text.splitlines() if l not in boiler]
            removed += len(p.text.splitlines()) - len(kept)
            p.text = "\n".join(kept)
    return out, removed


@dataclass
class Chunk:
    id: str
    url: str
    title: str
    heading: str
    text: str


def chunk_pages(pages: list[CleanPage], target_chars: int = 1200) -> list[Chunk]:
    """Split by headings, pack paragraphs up to ~target_chars (~300 tokens), keep URL/title/heading."""
    chunks = []
    for p in pages:
        heading, buf = p.title, []

        def flush():
            body = "\n".join(buf).strip()
            if body:
                cid = hashlib.sha1(f"{p.url}|{len(chunks)}|{body[:40]}".encode()).hexdigest()[:16]
                chunks.append(Chunk(cid, p.url, p.title, heading, (heading + "\n" + body) if heading else body))
            buf.clear()
        for line in p.text.splitlines():
            if re.match(r"^#{1,4} ", line):
                flush()
                heading = line.lstrip("# ").strip()
                continue
            if sum(len(x) for x in buf) + len(line) > target_chars:
                flush()
            buf.append(line)
        flush()
    return chunks
