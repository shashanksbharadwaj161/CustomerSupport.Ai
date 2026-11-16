import asyncio
import time

import pytest

from agent.knowledge.clean import chunk_pages, dedupe, html_to_text
from agent.knowledge.crawler import CrawlNotAllowed, Limits, crawl
from tests.conftest import make_client


def run_crawl(url, **kw):
    events = []

    async def emit(k, d):
        events.append((k, d))
    lim = Limits(delay_s=0, **kw)
    pages = asyncio.run(crawl(url, lim, emit))
    return pages, events


def test_bank_site_respects_robots_scope_and_limits(sites):
    pages, events = run_crawl(sites["lotus-bank"])
    urls = {p.url.rsplit("/", 1)[-1] for p in pages}
    assert {"", "accounts.html", "cards.html", "rates.html", "hours.html", "contact.html"} <= urls | {""}
    assert not any("private" in p.url for p in pages), "robots.txt disallows /private/"
    assert any(k == "skipped" and "robots" in d["reason"] for k, d in events)
    assert not any("example.com" in p.url for p in pages), "external links must be ignored"
    assert all(p.depth <= 3 for p in pages)
    only_home, _ = run_crawl(sites["lotus-bank"], max_depth=0)
    assert len(only_home) == 1
    two, _ = run_crawl(sites["lotus-bank"], max_pages=2)
    assert len(two) == 2


def test_cleaning_removes_nav_footer_and_chunks_keep_source(sites):
    pages, _ = run_crawl(sites["lotus-bank"])
    clean = [html_to_text(p.html, p.url) for p in pages]
    assert all("Partner site" not in c.text for c in clean), "footer dropped"
    clean, _ = dedupe(clean)
    chunks = chunk_pages(clean)
    assert len(chunks) >= 6
    hours = [c for c in chunks if "Saturday" in c.text]
    assert hours and hours[0].url.endswith("hours.html") and hours[0].title.startswith("Branches")
    assert not any("SECRET-STAFF-NOTE" in c.text for c in chunks)


def test_travel_site_includes_hindi_page(sites):
    pages, _ = run_crawl(sites["lotus-travel"])
    clean = [html_to_text(p.html, p.url) for p in pages]
    hi = [c for c in clean if c.lang == "hi"]
    assert hi and "शाकाहारी" in hi[0].text


def test_js_rendered_site(sites):
    pages, events = run_crawl(sites["lotus-js"])
    assert len(pages) == 2, "the services link only exists after JavaScript runs"
    assert all(p.rendered for p in pages)
    texts = [html_to_text(p.html, p.url).text for p in pages]
    assert all("JS-RENDERED" in t for t in texts)
    raw_pages, _ = run_crawl(sites["lotus-js"], render_js="never")
    assert "JS-RENDERED" not in html_to_text(raw_pages[0].html, raw_pages[0].url).text


def test_allowlist_blocks_other_hosts():
    async def emit(k, d):
        pass
    with pytest.raises(CrawlNotAllowed):
        asyncio.run(crawl("https://not-allowed.example/", Limits(), emit, allowlist=["lotusbay.example"]))


def _wait_ready(c, sid, timeout=120):
    after, events = 0, []
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = c.get(f"/api/knowledge/{sid}/events?mode=poll&after={after}").json()
        events += r["events"]
        if r["events"]:
            after = r["events"][-1]["id"]
        if r["status"] in ("ready", "error"):
            return r["status"], events
        time.sleep(0.3)
    raise TimeoutError


def test_api_ingest_retrieve_ask_attach_delete(data_dir, sites):
    from fastapi.testclient import TestClient
    _, app = make_client()
    with TestClient(app) as c:
        assert c.post("/api/knowledge", json={"url": sites["lotus-bank"]}).status_code == 400  # permission not confirmed
        sid = c.post("/api/knowledge", json={"url": sites["lotus-bank"], "permission_confirmed": True,
                                             "profile_id": "lotus-bank", "limits": {"max_pages": 20}}).json()["id"]
        status, events = _wait_ready(c, sid)
        assert status == "ready", events[-3:]
        kinds = [e["kind"] for e in events]
        for k in ("started", "robots", "page", "cleaned", "chunked", "embedded", "brief", "done"):
            assert k in kinds
        brief = next(e for e in events if e["kind"] == "brief")["data"]
        assert brief["status"] == "skipped" and "no API key" in brief["reason"]  # honest: no fake brief
        s = c.get(f"/api/knowledge/{sid}").json()
        assert s["pages"] >= 6 and s["chunks"] >= 6 and s["chunk_preview"]
        assert sid in c.get("/api/profiles/lotus-bank").json()["config"]["knowledge"]["source_ids"]
        ans = c.post(f"/api/knowledge/{sid}/ask", json={"question": "What are the Saturday opening hours of the branch?"}).json()
        assert ans["answer"] is None and "passages only" in ans["note"]
        assert ans["passages"][0]["url"].endswith("hours.html")
        # small site -> full text goes into the cached prompt (works without a key)
        sp = c.get("/api/profiles/lotus-bank/prompt").json()["system_prompt"]
        assert "Saturday: ten in the morning" in sp
        # SSE stream
        with c.stream("GET", f"/api/knowledge/{sid}/events") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            body = "".join(r.iter_text())
        assert "event: done" in body and "event: end" in body
        assert c.delete(f"/api/knowledge/{sid}").json()["ok"]
        assert sid not in c.get("/api/profiles/lotus-bank").json()["config"]["knowledge"]["source_ids"]


def test_retrieval_feeds_the_turn(data_dir, sites):
    from fastapi.testclient import TestClient
    from agent.brain import CallContext, TurnEngine
    from agent.llm.provider import FakeProvider
    _, app = make_client()
    with TestClient(app) as c:
        sid = c.post("/api/knowledge", json={"url": sites["lotus-travel"], "permission_confirmed": True}).json()["id"]
        assert _wait_ready(c, sid)[0] == "ready"
        ks = app.state.knowledge
        prof = app.state.profiles.get("lotus-travel")["config"]
        prof["knowledge"]["source_ids"] = [sid]
        prof["knowledge"]["min_score"] = 0.0
        prov = FakeProvider(script=lambda m, s: "The cruise departs at six thirty in the evening.")
        out = []

        async def emit(k, d):
            out.append((k, d))
        meta = asyncio.run(TurnEngine(CallContext("t", prof), prov, "m", retriever=ks).respond(
            "When does the evening river cruise depart?", "en", emit))
        assert meta["sources"] and any("cruise" in (s["url"] or "") for s in meta["sources"])
        assert "passage 1 from" in prov.calls[0]["messages"][-1]["content"]
        assert any(k == "sources" for k, _ in out)


def test_exposed_mode_requires_allowlist(data_dir, sites, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("SHAON_EXPOSED", "1")
    monkeypatch.setenv("CRAWL_ALLOWLIST", "lotusbay.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    _, app = make_client()
    with TestClient(app) as c:
        h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"password": "pw"}).json()["token"]}
        sid = c.post("/api/knowledge", json={"url": "https://elsewhere.example/", "permission_confirmed": True}, headers=h).json()["id"]
        for _ in range(50):
            r = c.get(f"/api/knowledge/{sid}/events?mode=poll", headers=h).json()
            if r["status"] == "error":
                break
            time.sleep(0.1)
        assert r["status"] == "error" and "allowlist" in r["events"][-1]["data"]["error"]
