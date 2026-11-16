"""FastAPI app: REST API + call transports + the exported web UI on ONE port (one tunnel, DEPLOY.md).

Run: uvicorn --factory api.main:create_app --port 8000   (scripts/start.sh does this)
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent import logscrub
from api.auth import PUBLIC, Auth
from api.profiles import ProfileStore
from api.state import AppState, require_admin


def create_app(state: AppState | None = None) -> FastAPI:
    logscrub.install()
    st = state or AppState()
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_app):
        _preload(st)
        seed = asyncio.create_task(_seed_demo_knowledge(app))
        yield
        seed.cancel()

    app = FastAPI(title="ShaOn Voice AI", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.app = st
    app.state.auth = Auth(st.cfg.admin_password, st.secrets.key_file.read_bytes(), st.cfg.allowed_origins)
    app.state.profiles = ProfileStore(st.db)
    app.state.profiles.seed()
    _optional_modules(app)

    @app.middleware("http")
    async def auth_mw(request: Request, call_next):
        p = request.url.path
        if p.startswith("/api/") and p not in PUBLIC and not p.startswith("/api/docs") and p != "/api/openapi.json":
            if app.state.auth.enabled and not app.state.auth.token_ok(Auth.token_from(request)):
                return JSONResponse({"detail": "Login required."}, status_code=401)
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

    @app.exception_handler(Exception)
    async def scrubbed_errors(request: Request, exc: Exception):  # never leak keys in error bodies
        logging.getLogger("shaon").exception("unhandled error")
        return JSONResponse({"detail": logscrub.scrub(f"{type(exc).__name__}: {exc}")[:300]}, status_code=500)

    # ---- auth
    @app.get("/api/auth/status")
    def auth_status(request: Request):
        return {"required": app.state.auth.enabled, "ok": app.state.auth.token_ok(Auth.token_from(request))}

    @app.post("/api/auth/login")
    async def login(request: Request):
        app.state.auth.rate_limit(request, "login")
        body = await request.json()
        token = app.state.auth.login(str(body.get("password", "")))
        resp = JSONResponse({"token": token, "required": app.state.auth.enabled})
        if token:
            resp.set_cookie("shaon_token", token, httponly=True, samesite="strict", max_age=12 * 3600,
                            secure=request.url.scheme == "https")
        return resp

    # ---- health / engines
    @app.get("/api/health")
    def health():
        h = st.health()
        if app.state.auth.enabled:  # public endpoint: keep it minimal when auth is on
            return {"mode": h["mode"], "reasons": h["reasons"], "auth_required": True}
        return h

    @app.get("/api/engines")
    def engines():
        return {**st.engines.status(), "config": st.engines.cfg}

    # ---- settings (key never leaves the server; last 4 only)
    @app.get("/api/settings")
    def get_settings():
        key, source = st.secrets.api_key()
        return {"key_present": bool(key), "key_source": source, "key_last4": st.secrets.last4(key),
                "key_edit_allowed": st.cfg.allow_key_edit, "admin_password_set": bool(st.cfg.admin_password),
                "spend": st.spend.summary(), "provider": st.provider().name, "model": st.cfg.llm_model,
                "fallback_model": st.cfg.llm_fallback_model, "transport": st.cfg.transport}

    @app.put("/api/settings/key")
    async def put_key(request: Request):
        require_admin(st, request, for_key=True)
        body = await request.json()
        key = str(body.get("key", "")).strip()
        if not key.startswith("sk-ant-") or len(key) < 20:
            raise HTTPException(400, "That does not look like an Anthropic API key (sk-ant-...).")
        logscrub.register_secret(key)
        st.secrets.set("anthropic_api_key", key)
        st._provider_cache = None
        return {"ok": True, "key_last4": key[-4:]}

    @app.delete("/api/settings/key")
    async def del_key(request: Request):
        require_admin(st, request, for_key=True)
        st.secrets.delete("anthropic_api_key")
        st._provider_cache = None
        return {"ok": True}

    @app.post("/api/settings/key/test")
    async def test_key(request: Request):
        require_admin(st, request)
        prov = st.provider()
        if not hasattr(prov, "test_key"):
            raise HTTPException(400, f"No real key to test (provider: {prov.name}).")
        try:
            return await asyncio.wait_for(prov.test_key(), timeout=30)
        except HTTPException:
            raise
        except Exception as e:
            return JSONResponse({"ok": False, "error": logscrub.scrub(f"{type(e).__name__}: {e}")[:300]}, status_code=400)

    @app.put("/api/settings/spend-cap")
    async def put_cap(request: Request):
        require_admin(st, request)
        body = await request.json()
        try:
            st.spend.set_cap(float(body["cap_usd"]))
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "cap_usd must be a number >= 0")
        return st.spend.summary()

    # ---- calls + logs
    from api.calls import router as calls_router
    app.include_router(calls_router(app))
    from api.routes import register
    register(app)
    from api.voices import register as register_voices
    register_voices(app)
    if app.state.knowledge is not None:
        from api.knowledge import register as register_knowledge
        register_knowledge(app)

    # ---- web UI (static export). Mounted last so /api wins.
    web = st.cfg.web_dir
    if web.exists():
        @app.get("/logs/{rest:path}", include_in_schema=False)
        def logs_page(rest: str):
            return FileResponse(web / "logs" / "index.html")
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        def no_web():
            return JSONResponse({"detail": "web UI not built: run `cd web && npm run build` (scripts/start.sh does it)"})
    return app


async def _seed_demo_knowledge(app) -> None:
    """First start: crawl the two bundled FAKE demo sites and attach them to the two demo agents (M8).
    Disable with SHAON_SEED_DEMO=0. Uses the app's own URL so source links keep working."""
    import os
    st = app.state.app
    ks = app.state.knowledge
    if ks is None or (os.environ.get("SHAON_SEED_DEMO") or "1") == "0":
        return
    if st.db.one("SELECT id FROM knowledge_sources LIMIT 1"):
        return
    await asyncio.sleep(3)  # let the server start listening
    base = (os.environ.get("SHAON_SELF_URL") or "http://127.0.0.1:8000").rstrip("/")
    from agent.knowledge.crawler import Limits
    for site, pid in (("lotus-bank", "lotus-bank"), ("lotus-travel", "lotus-travel")):
        try:
            sid = ks.start(f"{base}/demo-sites/{site}/", Limits(max_depth=2, max_pages=20, render_js="never", delay_s=0), pid, sid=f"demo_{site}")
            p = app.state.profiles.get(pid)
            if p and sid not in p["config"]["knowledge"]["source_ids"]:
                p["config"]["knowledge"]["source_ids"].append(sid)
                app.state.profiles.save(pid, p["config"], note=f"attach demo site {site}")
        except Exception as e:
            logging.getLogger("shaon").warning("demo seed %s failed: %s", site, e)


def _preload(st) -> None:
    """SHAON_PRELOAD=stt:en,tts:en,stt:ja ... loads engines in the background so call one is not slow."""
    import threading

    def work():
        for item in st.cfg.preload:
            kind, _, lang = item.partition(":")
            try:
                if kind == "stt":
                    name, opts = st.engines.stt_choice(lang or "en")
                    st.engines.get_stt(name, opts)
                elif kind == "tts":
                    vid = st.engines.cfg["default_voices"].get(lang or "en")
                    v = st.voices().voice(vid) if vid else None
                    if v:
                        st.engines.get_tts(v.engine).synthesize("Ready.", v)
                elif kind == "lid":
                    st.engines.lid_engine()
            except Exception as e:
                logging.getLogger("shaon").warning("preload %s failed: %s", item, e)
    if st.cfg.preload:
        threading.Thread(target=work, daemon=True).start()


def _optional_modules(app: FastAPI) -> None:
    """Knowledge (M4), guardrails (M5), voices (M6) attach themselves here when available."""
    st = app.state.app
    try:
        from api.knowledge import KnowledgeService
        app.state.knowledge = KnowledgeService(st)
        app.state.retriever = app.state.knowledge
    except ImportError:
        app.state.knowledge = None
        app.state.retriever = None
    try:
        from agent.guardrails import Guardrails
        app.state.guard = Guardrails()
    except ImportError:
        app.state.guard = None


# run with: uvicorn --factory api.main:create_app
