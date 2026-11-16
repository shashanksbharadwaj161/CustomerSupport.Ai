"""Knowledge service: crawl -> clean -> chunk -> embed (Chroma) -> brief; retrieval for calls; REST + SSE/polling."""
from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent.knowledge.brief import BRIEF_SYSTEM, brief_prompt
from agent.knowledge.clean import chunk_pages, dedupe, html_to_text
from agent.knowledge.crawler import CrawlNotAllowed, Limits, crawl
from agent.knowledge.embed import get_embedder
from agent.knowledge.store import VectorStore
from api.config import ROOT
from api.db import dumps, now

SMALL_SITE_CHARS = 12000  # PLAN 8.9: small sites go fully into the cached prompt
DEMO_SITES = ROOT / "eval" / "fixtures" / "sites"


class KnowledgeService:
    def __init__(self, state):
        self.st = state
        self.db = state.db
        self.store = VectorStore(state.cfg.data_dir / "chroma")
        self.tasks: dict[str, asyncio.Task] = {}

    # ---------- events (one log, read by SSE and by the polling fallback)
    def event(self, sid: str, kind: str, data: dict) -> None:
        self.db.execute("INSERT INTO knowledge_events(source_id,kind,data_json,created_at) VALUES(?,?,?,?)", (sid, kind, dumps(data), now()))

    def events(self, sid: str, after: int = 0) -> list[dict]:
        rows = self.db.all("SELECT id,kind,data_json,created_at FROM knowledge_events WHERE source_id=? AND id>? ORDER BY id", (sid, after))
        return [{"id": r["id"], "kind": r["kind"], "data": json.loads(r["data_json"]), "t": r["created_at"]} for r in rows]

    # ---------- crawl job
    def allowlist(self) -> list[str] | None:
        if not self.st.cfg.exposed and not self.st.cfg.crawl_allowlist:
            return None
        return self.st.cfg.crawl_allowlist + ["127.0.0.1", "localhost"]

    def start(self, url: str, limits: Limits, profile_id: str | None = None, sid: str | None = None) -> str:
        sid = sid or "src_" + uuid.uuid4().hex[:10]
        if not self.db.one("SELECT id FROM knowledge_sources WHERE id=?", (sid,)):
            self.db.execute("INSERT INTO knowledge_sources(id,profile_id,url,status,limits_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                            (sid, profile_id, url, "queued", dumps(limits.__dict__), now(), now()))
        else:
            self.db.execute("UPDATE knowledge_sources SET status='queued', error=NULL, updated_at=? WHERE id=?", (now(), sid))
        self.tasks[sid] = asyncio.create_task(self._run(sid, url, limits))
        return sid

    async def _run(self, sid: str, url: str, limits: Limits) -> None:
        def upd(**f):
            f["updated_at"] = now()
            self.db.execute(f"UPDATE knowledge_sources SET {', '.join(k + '=?' for k in f)} WHERE id=?", (*f.values(), sid))

        async def emit(kind, data):
            self.event(sid, kind, data)
        try:
            upd(status="crawling")
            await emit("started", {"url": url, "limits": limits.__dict__})
            pages = await crawl(url, limits, emit, allowlist=self.allowlist())
            upd(status="cleaning", pages=len(pages))
            clean = [html_to_text(p.html, p.url) for p in pages]
            clean, removed = dedupe(clean)
            self.db.execute("DELETE FROM knowledge_pages WHERE source_id=?", (sid,))
            for p, raw in zip(clean, pages):
                self.db.execute("INSERT INTO knowledge_pages(source_id,url,title,depth,rendered,chars,text,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                (sid, p.url, p.title, raw.depth, int(raw.rendered), len(p.text), p.text, now()))
            await emit("cleaned", {"pages": len(clean), "boilerplate_lines_removed": removed})
            chunks = chunk_pages(clean)
            await emit("chunked", {"chunks": len(chunks)})
            upd(status="embedding", chunks=len(chunks))
            emb = await asyncio.to_thread(get_embedder)
            vecs = await asyncio.to_thread(emb.encode, [c.text for c in chunks]) if chunks else None
            if chunks:
                await asyncio.to_thread(self.store.replace, sid, [c.id for c in chunks], vecs, [c.text for c in chunks],
                                        [{"url": c.url, "title": c.title, "heading": c.heading} for c in chunks])
            upd(embedder=emb.name)
            await emit("embedded", {"chunks": len(chunks), "embedder": emb.name})
            upd(status="brief")
            await self._brief(sid, clean, emit, upd)
            upd(status="ready")
            await emit("done", {"pages": len(clean), "chunks": len(chunks)})
        except CrawlNotAllowed as e:
            upd(status="error", error=str(e))
            await emit("error", {"error": str(e)})
        except Exception as e:  # never crash the server on a bad site
            from agent.logscrub import scrub
            upd(status="error", error=scrub(f"{type(e).__name__}: {e}")[:300])
            await emit("error", {"error": scrub(str(e))[:300]})

    async def _brief(self, sid, clean, emit, upd) -> None:
        prov = self.st.provider()
        total = sum(len(p.text) for p in clean)
        if not prov.is_real:
            upd(brief_status=f"pending: no language model ({prov.name})", brief_text=None)
            await emit("brief", {"status": "skipped", "reason": f"no API key / {prov.name} provider",
                                 "small_site_full_text": total <= SMALL_SITE_CHARS})
            return
        try:
            r = await prov.stream(system=BRIEF_SYSTEM, messages=[{"role": "user", "content": brief_prompt(clean)}],
                                  max_tokens=1200, purpose="site_brief")
            upd(brief_status="ok", brief_text=r.text)
            await emit("brief", {"status": "ok", "chars": len(r.text)})
        except Exception as e:
            from agent.logscrub import scrub
            upd(brief_status="error: " + scrub(str(e))[:200])
            await emit("brief", {"status": "error", "error": scrub(str(e))[:200]})

    # ---------- retrieval (TurnEngine Retriever protocol)
    def search(self, text: str, profile: dict, k: int = 4) -> list[dict]:
        sids = profile.get("knowledge", {}).get("source_ids", [])
        if not sids:
            return []
        rows = self.db.all(f"SELECT id, embedder FROM knowledge_sources WHERE id IN ({','.join('?' * len(sids))}) AND status='ready'", tuple(sids))
        if not rows:
            return []
        hits = []
        for r in rows:
            emb = get_embedder("bge-m3" if r["embedder"] == "BAAI/bge-m3" else "hash")
            vec = emb.encode([text])[0]
            hits += self.store.query(r["id"], vec, k)
        min_score = float(profile.get("knowledge", {}).get("min_score", 0.35))
        hits = [h for h in sorted(hits, key=lambda h: -h["score"]) if h["score"] >= min_score]
        return hits[:k]

    def context_for(self, profile: dict) -> dict:
        sids = profile.get("knowledge", {}).get("source_ids", [])
        if not sids:
            return {}
        briefs, texts = [], []
        for sid in sids:
            s = self.db.one("SELECT * FROM knowledge_sources WHERE id=? AND status='ready'", (sid,))
            if not s:
                continue
            if s.get("brief_text"):
                briefs.append(f"[{s['url']}]\n{s['brief_text']}")
            pages = self.db.all("SELECT url, title, text FROM knowledge_pages WHERE source_id=? ORDER BY id", (sid,))
            total = sum(len(p["text"]) for p in pages)
            if total <= SMALL_SITE_CHARS:
                texts.append("\n\n".join(f"=== {p['title']} ({p['url']})\n{p['text']}" for p in pages))
        return {"brief": "\n\n".join(briefs) or None, "kb_text": "\n\n".join(texts) or None}


def register(app: FastAPI) -> None:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import PlainTextResponse

    st = app.state.app
    ks: KnowledgeService = app.state.knowledge

    if DEMO_SITES.exists():
        app.mount("/demo-sites", StaticFiles(directory=DEMO_SITES, html=True), name="demo-sites")

    @app.get("/robots.txt", include_in_schema=False)
    def robots():  # the app's own robots.txt also covers the demo sites served under /demo-sites/
        return PlainTextResponse("User-agent: *\nDisallow: /api/\nDisallow: /demo-sites/lotus-bank/private/\n")

    @app.get("/api/knowledge")
    def list_sources(profile_id: str | None = None):
        q = "SELECT id,profile_id,url,status,pages,chunks,brief_status,embedder,error,created_at,updated_at FROM knowledge_sources"
        return st.db.all(q + (" WHERE profile_id=?" if profile_id else "") + " ORDER BY created_at DESC", (profile_id,) if profile_id else ())

    @app.post("/api/knowledge")
    async def create(request: Request):
        app.state.auth.rate_limit(request, "crawl")
        body = await request.json()
        url = str(body.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "URL must start with http:// or https://")
        if not body.get("permission_confirmed"):
            raise HTTPException(400, "Confirm you own this site or have permission to crawl it.")
        lim = body.get("limits") or {}
        limits = Limits(max_depth=max(0, min(int(lim.get("max_depth", 3)), 5)), max_pages=max(1, min(int(lim.get("max_pages", 50)), 200)),
                        render_js=lim.get("render_js", "auto") if lim.get("render_js") in ("auto", "always", "never") else "auto")
        sid = ks.start(url, limits, body.get("profile_id"))
        pid = body.get("profile_id")
        if pid and body.get("attach", True):  # attach to the agent (new profile version)
            p = app.state.profiles.get(pid)
            if p and sid not in p["config"]["knowledge"]["source_ids"]:
                p["config"]["knowledge"]["source_ids"].append(sid)
                app.state.profiles.save(pid, p["config"], note=f"attach knowledge {sid}")
        return {"id": sid}

    @app.get("/api/knowledge/{sid}")
    def get(sid: str):
        s = st.db.one("SELECT * FROM knowledge_sources WHERE id=?", (sid,))
        if not s:
            raise HTTPException(404, "source not found")
        s["pages_list"] = st.db.all("SELECT url,title,depth,rendered,chars FROM knowledge_pages WHERE source_id=? ORDER BY id", (sid,))
        s["chunk_preview"] = ks.store.peek(sid, 12)
        return s

    @app.get("/api/knowledge/{sid}/events")
    async def events(sid: str, request: Request, after: int = 0, mode: str = "sse"):
        """SSE stream; `?mode=poll&after=N` returns JSON for the polling fallback (Quick Tunnels do not support SSE)."""
        if mode == "poll":
            s = st.db.one("SELECT status FROM knowledge_sources WHERE id=?", (sid,))
            return {"status": s["status"] if s else None, "events": ks.events(sid, after)}

        async def gen():
            last = after
            for _ in range(1200):  # max ~10 minutes
                if await request.is_disconnected():
                    break
                evs = ks.events(sid, last)
                for e in evs:
                    last = e["id"]
                    yield f"id: {e['id']}\nevent: {e['kind']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                s = st.db.one("SELECT status FROM knowledge_sources WHERE id=?", (sid,))
                if not s or s["status"] in ("ready", "error"):
                    yield f"event: end\ndata: {json.dumps({'status': s['status'] if s else None})}\n\n"
                    break
                await asyncio.sleep(0.5)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/knowledge/{sid}/ask")
    async def ask(sid: str, request: Request):
        app.state.auth.rate_limit(request, "ask")
        body = await request.json()
        q = str(body.get("question", "")).strip()
        if not q:
            raise HTTPException(400, "question required")
        prof = {"knowledge": {"source_ids": [sid], "min_score": float(body.get("min_score", 0.0))}}
        t0 = time.perf_counter()
        hits = await asyncio.to_thread(ks.search, q, prof, int(body.get("top_k", 4)))
        out = {"question": q, "passages": hits, "retrieval_ms": round((time.perf_counter() - t0) * 1000)}
        prov = st.provider()
        if not prov.is_real:
            out.update(answer=None, note=f"No language model ({prov.name}): showing retrieved passages only.")
            return out
        from agent.llm.prompt import turn_context
        s = st.db.one("SELECT brief_text FROM knowledge_sources WHERE id=?", (sid,))
        sysmsg = ("Answer the question in one or two sentences using ONLY the passages and brief. "
                  "If they do not contain the answer, say you do not know. Reply in the question's language.\n\nBrief:\n" + (s.get("brief_text") or "none"))
        r = await prov.stream(system=sysmsg, messages=[{"role": "user", "content": turn_context("auto", hits) + q}], max_tokens=300, purpose="kb_ask")
        out.update(answer=r.text, model=r.model)
        return out

    @app.post("/api/knowledge/{sid}/recrawl")
    def recrawl(sid: str, request: Request):
        app.state.auth.rate_limit(request, "crawl")
        s = st.db.one("SELECT * FROM knowledge_sources WHERE id=?", (sid,))
        if not s:
            raise HTTPException(404, "source not found")
        ks.start(s["url"], Limits(**json.loads(s["limits_json"] or "{}")), s["profile_id"], sid=sid)
        return {"id": sid}

    @app.delete("/api/knowledge/{sid}")
    def delete(sid: str):
        t = ks.tasks.pop(sid, None)
        if t and not t.done():
            t.cancel()
        ks.store.delete(sid)
        for tbl in ("knowledge_pages", "knowledge_events"):
            st.db.execute(f"DELETE FROM {tbl} WHERE source_id=?", (sid,))
        st.db.execute("DELETE FROM knowledge_sources WHERE id=?", (sid,))
        for p in st.db.all("SELECT id FROM profiles"):
            prof = app.state.profiles.get(p["id"])
            if sid in prof["config"]["knowledge"]["source_ids"]:
                prof["config"]["knowledge"]["source_ids"].remove(sid)
                app.state.profiles.save(p["id"], prof["config"], note=f"detach deleted knowledge {sid}")
        return {"ok": True}
