"""M4 TEST: cross-lingual retrieval through the real ingestion pipeline (crawl -> clean -> chunk -> embed -> Chroma).

Crawls the two fake sites (served locally), then asks every test line whose topic has an answer page.
  SHAON_EMBEDDER=bge-m3 python -m eval.runners.run_kb
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import os
import tempfile
import threading

import numpy as np

from agent.knowledge.clean import chunk_pages, dedupe, html_to_text
from agent.knowledge.crawler import Limits, crawl
from agent.knowledge.embed import get_embedder
from agent.knowledge.store import VectorStore
from eval.common import ROOT, load_lines, save

ANSWER_PAGE = {"balance": "accounts.html", "transfer": "accounts.html", "card_block": "cards.html",
               "double_charge": "cards.html", "fd_rate": "rates.html", "branch_hours": "hours.html",
               "human_agent": "contact.html", "tour_booking": "tours.html", "cruise_food": "cruise.html"}


def serve(name):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "eval/fixtures/sites" / name))
    h.log_message = lambda *a, **k: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}/"


async def ingest(url):
    async def emit(k, d):
        pass
    pages = await crawl(url, Limits(delay_s=0, render_js="never"), emit)
    clean, _ = dedupe([html_to_text(p.html, p.url) for p in pages])
    return chunk_pages(clean)


def main():
    emb = get_embedder(os.environ.get("SHAON_EMBEDDER") or "auto")
    store = VectorStore(__import__("pathlib").Path(tempfile.mkdtemp()))
    for name in ("lotus-bank", "lotus-travel"):
        srv, url = serve(name)
        chunks = asyncio.run(ingest(url))
        store.replace(name, [c.id for c in chunks], emb.encode([c.text for c in chunks]), [c.text for c in chunks],
                      [{"url": c.url, "title": c.title, "heading": c.heading} for c in chunks])
        srv.shutdown()
    rows = []
    for l in load_lines():
        if l["topic"] not in ANSWER_PAGE:
            continue
        v = emb.encode([l["text"]])[0]
        hits = sorted(store.query("lotus-bank", v, 3) + store.query("lotus-travel", v, 3), key=lambda h: -h["score"])[:3]
        pages = [h["url"].rsplit("/", 1)[-1] for h in hits]
        rows.append({"id": l["id"], "lang": l["lang"], "category": l["category"], "topic": l["topic"], "top3": pages,
                     "hit1": pages[0] == ANSWER_PAGE[l["topic"]], "hit3": ANSWER_PAGE[l["topic"]] in pages, "score1": hits[0]["score"]})
    per = {}
    for lang in ("en", "ja", "hi", "bn", "kn"):
        rs = [r for r in rows if r["lang"] == lang and r["category"] == "mono"]
        if rs:
            per[lang] = {"n": len(rs), "hit1": round(np.mean([r["hit1"] for r in rs]), 3), "hit3": round(np.mean([r["hit3"] for r in rs]), 3)}
            print(lang, per[lang])
    mixed = [r for r in rows if r["category"] != "mono"]
    p = save("kb_retrieval", {"kind": "kb_retrieval", "embedder": emb.name, "per_lang": per,
                              "mixed": {"n": len(mixed), "hit1": round(float(np.mean([r["hit1"] for r in mixed])), 3) if mixed else None},
                              "rows": rows})
    print("mixed", len(mixed), "saved", p)


if __name__ == "__main__":
    main()
