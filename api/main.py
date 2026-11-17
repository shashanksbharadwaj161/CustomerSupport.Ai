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
from api.auth import Auth, client_ip, has_forwarding_headers, required_role
from api.profiles import ProfileStore
from api.state import AppState, is_loopback, require_admin


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
    app.state.auth = Auth(st.cfg.admin_password, st.secrets.key_file.read_bytes(), st.cfg.allowed_origins,
                          visitor_passcode=st.cfg.visitor_passcode, exposed=st.cfg.exposed, share_host_file=st.cfg.share_host_file)
    for s in (st.cfg.admin_password, st.cfg.visitor_passcode):
        logscrub.register_secret(s)  # passcodes never appear in logs
    app.state.profiles = ProfileStore(st.db)
    app.state.profiles.seed()
    _optional_modules(app)

    @app.middleware("http")
    async def auth_mw(request: Request, call_next):
        auth: Auth = app.state.auth
        p = request.url.path
        # local preview has NO passcodes, so it answers only this PC: direct loopback, never through a proxy/tunnel
        if st.cfg.local_preview and not is_loopback(request):
            return JSONResponse({"detail": "Local preview only answers this PC (127.0.0.1). For a public link use ShaOn-Share.bat."},
                                status_code=403)
        # exposed: Host must be localhost or the tunnel host learned at launch (blocks DNS-rebinding / stray hosts),
        # and browser-sent Origin on state-changing requests must match too
        if not auth.host_ok(request.headers.get("host")):
            return JSONResponse({"detail": "Unknown host."}, status_code=421)
        if auth.exposed and request.method not in ("GET", "HEAD", "OPTIONS") and \
                not auth.origin_ok(request.headers.get("origin"), request.headers.get("host")):
            return JSONResponse({"detail": "Origin not allowed."}, status_code=403)
        need = required_role(request.method, p)
        if need in ("visitor", "admin") and auth.enabled and not auth.token_ok(Auth.token_from(request), need):
            known = auth.role_from(request) is not None
            return JSONResponse({"detail": "Admin passcode required." if known else "Login required."}, status_code=403 if known else 401)
        if auth.exposed and p.startswith("/api/") and not auth.rate_limit_key(client_ip(request), "api"):
            return JSONResponse({"detail": "Too many requests."}, status_code=429)
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
        a: Auth = app.state.auth
        role = a.role_from(request)
        return {"required": a.enabled, "ok": role is not None, "role": role, "visitor_mode": a.roles_on,
                "share": st.cfg.exposed, "local_preview": st.cfg.local_preview}

    @app.post("/api/auth/login")
    async def login(request: Request):
        app.state.auth.rate_limit(request, "login")
        body = await request.json()
        token, role = app.state.auth.login(str(body.get("passcode", body.get("password", ""))))
        resp = JSONResponse({"token": token, "role": role, "required": app.state.auth.enabled})
        if token:
            resp.set_cookie("shaon_token", token, httponly=True, samesite="strict", max_age=12 * 3600,
                            secure=request.url.scheme == "https" or has_forwarding_headers(request.headers))
        return resp

    @app.post("/api/auth/logout")
    def logout():
        resp = JSONResponse({"ok": True})
        resp.delete_cookie("shaon_token")
        return resp

    # ---- health / readiness
    @app.get("/health")
    def health_public():
        return {"ok": True, "share": st.cfg.exposed}

    @app.get("/api/health")
    def health():
        h = st.health()
        if app.state.auth.enabled:  # public endpoint: keep it minimal when auth is on
            return {"mode": h["mode"], "reasons": h["reasons"], "auth_required": True, "notes": h["notes"][:1]}
        return h

    @app.get("/api/ready")
    def ready():
        return st.readiness()

    @app.get("/api/share/status")
    def share_status(request: Request):
        """For the launcher only: direct loopback, no tunnel headers."""
        peer = request.client.host if request.client else ""
        if has_forwarding_headers(request.headers) or peer not in ("127.0.0.1", "::1", "localhost", "testclient"):
            raise HTTPException(404, "Not found")
        r = st.readiness()
        key, _src = st.secrets.api_key()
        return {**r, "spend": st.spend.summary(), "share_host": app.state.auth.share_host(),
                "key_present": bool(key)}  # a yes/no for the launcher's first-run step; never the key itself

    @app.get("/api/engines")
    def engines():
        return {**st.engines.status(), "config": st.engines.cfg}

    # ---- settings (key never leaves the server; last 4 only)
    def model_block() -> dict:
        from agent.llm.models import CATALOG_SOURCE, merge_live
        live, live_at = st.live_models()
        ms = st.model_settings()
        prov = st.provider()
        return {"model": ms["llm_model"], "model_source": ms["llm_model_source"], "model_known": ms["llm_model_known"],
                "fallback_model": ms["llm_fallback_model"], "fallback_source": ms["llm_fallback_model_source"],
                "fallback_known": ms["llm_fallback_model_known"],
                "active_model": ms["llm_model"] if prov.is_real else None,  # what replies are sent to right now
                "provider": prov.name, "catalog": merge_live(live), "catalog_source": CATALOG_SOURCE,
                "live_listed_at": live_at, "live_count": len(live)}

    @app.get("/api/settings")
    def get_settings():
        key, source = st.secrets.api_key()
        return {"key_present": bool(key), "key_source": source, "key_last4": st.secrets.last4(key),
                "key_edit_allowed": st.cfg.allow_key_edit, "admin_password_set": bool(st.cfg.admin_password),
                "local_preview": st.cfg.local_preview, "share": st.cfg.exposed,
                "spend": st.spend.summary(), **model_block(), "transport": st.cfg.transport}

    @app.put("/api/settings/key")
    async def put_key(request: Request):
        require_admin(st, request, for_key=True)
        body = await request.json()
        key = str(body.get("key", "")).strip()
        if not key.startswith("sk-ant-") or len(key) < 20 or any(c.isspace() for c in key):
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
        key, source = st.secrets.api_key()
        return {"ok": True, "key_present": bool(key), "key_source": source}  # an .env key may still apply

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
            return JSONResponse({"ok": False, "error": _friendly_llm_error(e, st.llm_model())}, status_code=400)

    @app.put("/api/settings/model")
    async def put_model(request: Request):
        """Main + fallback model. Known = in the docs catalog or this key's live model list; anything else needs
        allow_unlisted=true and is marked unverified until a Test key / call succeeds with it."""
        require_admin(st, request)
        from agent.llm.models import valid_id_format
        body = await request.json()
        model = str(body.get("model", "")).strip()
        fb = str(body.get("fallback_model", "") or "").strip()
        known = {m["id"] for m in model_block()["catalog"]}
        for label, v in (("model", model), ("fallback model", fb)):
            if label == "fallback model" and not v:
                continue
            if not valid_id_format(v):
                raise HTTPException(400, f"The {label} ID '{v[:80]}' is not a valid model ID (lowercase letters, digits, dashes).")
            if v not in known and not body.get("allow_unlisted"):
                raise HTTPException(400, f"'{v}' is not in the model list. Refresh the list with your key, or tick "
                                         "'use this exact ID' to save it unverified (Test key then checks it).")
        if fb and fb == model:
            fb = ""
        st.set_models(model, fb or None)
        return model_block()

    @app.post("/api/settings/models/refresh")
    async def refresh_models(request: Request):
        """Live model list for THIS key (Models API: free, no tokens). Only runs when the user presses Refresh."""
        require_admin(st, request)
        prov = st.provider()
        if not hasattr(prov, "list_models"):
            raise HTTPException(400, "Add an API key first: the live model list comes from your Anthropic account.")
        try:
            live = await asyncio.wait_for(prov.list_models(), timeout=30)
        except Exception as e:
            return JSONResponse({"ok": False, "error": _friendly_llm_error(e, None)}, status_code=400)
        st.save_live_models(live)
        return model_block()

    @app.put("/api/settings/spend-cap")
    async def put_cap(request: Request):
        require_admin(st, request)
        body = await request.json()
        try:
            st.spend.set_cap(float(body["cap_usd"]))
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "The cap must be a number from 0 to 100000 (USD).")
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


def _friendly_llm_error(e: Exception, model: str | None) -> str:
    """Plain-language Anthropic API errors for Settings (scrubbed: never contains the key)."""
    import anthropic
    from api.spend import SpendCapReached
    if isinstance(e, SpendCapReached):
        return f"Spend cap reached ({e}). Raise the cap below to make Claude calls again."
    if isinstance(e, anthropic.AuthenticationError):
        return "Anthropic rejected the key (401). Check that it was copied completely and is still active."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "This key is not allowed to use that resource (403)."
    if isinstance(e, anthropic.NotFoundError):
        return f"Model '{model}' was not found for this key (404). Pick another model or refresh the model list."
    if isinstance(e, anthropic.RateLimitError):
        return "Rate limited by Anthropic (429). Wait a minute and try again."
    if isinstance(e, anthropic.BadRequestError):
        return logscrub.scrub(f"Anthropic refused the request (400): {getattr(e, 'message', e)}")[:300]
    if isinstance(e, (anthropic.APIConnectionError, asyncio.TimeoutError)):
        return "Could not reach the Anthropic API (network or timeout)."
    return logscrub.scrub(f"{type(e).__name__}: {e}")[:300]


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
                    st.engines.warm_stt(lang or "en")
                elif kind == "tts":  # default voice, else the CPU fallbacks in order (what a call would use)
                    cat = st.voices()
                    ids = [st.engines.cfg["default_voices"].get(lang or "en")]
                    fb = st.engines.cfg.get("cpu_fallback_voices", {}).get(lang or "en") or []
                    ids += [fb] if isinstance(fb, str) else fb
                    for vid in [i for i in ids if i]:
                        v = cat.voice(vid)
                        try:
                            st.engines.get_tts(v.engine).synthesize(cat.ref_text.get(v.language, "Ready."), v)
                            break
                        except Exception:
                            continue
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
