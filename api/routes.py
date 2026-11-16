"""REST routes: profiles (M2), calls/logs (M1/M8). Knowledge and voices routes register in their modules."""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Request

from agent.presets import PRESETS


def validate_config(cfg) -> list[str]:
    """Shape checks before a profile is saved (the normalizer fills defaults afterwards)."""
    from agent.presets import LANGS, TOOLS_BY_TYPE
    errs = []
    if not isinstance(cfg, dict):
        return ["config must be an object"]
    if cfg.get("type") not in TOOLS_BY_TYPE:
        errs.append(f"type must be one of {sorted(TOOLS_BY_TYPE)}")
    langs = (cfg.get("languages") or {}).get("enabled", [])
    if not isinstance(langs, list) or not langs or any(l not in LANGS for l in langs):
        errs.append(f"languages.enabled must be a non-empty subset of {LANGS}")
    ms = (cfg.get("response_style") or {}).get("max_sentences", 2)
    if not isinstance(ms, int) or not 1 <= ms <= 4:
        errs.append("response_style.max_sentences must be 1-4")
    for k in ("allowed_topics", "forbidden_topics", "banned_claims", "escalation_triggers"):
        v = (cfg.get("guardrails") or {}).get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"guardrails.{k} must be a list of strings")
    bad = [t for t in cfg.get("tools", []) if t not in TOOLS_BY_TYPE.get(cfg.get("type"), [])]
    if bad:
        errs.append(f"tools not allowed for type {cfg.get('type')}: {bad}")
    if len(str(cfg.get("custom_role_text", ""))) > 4000:
        errs.append("custom_role_text too long (4000 chars max)")
    return errs


def register(app: FastAPI) -> None:
    st = app.state.app
    profiles = app.state.profiles

    # ---- profiles
    @app.get("/api/presets")
    def presets():
        return profiles.presets()

    @app.get("/api/profiles")
    def list_profiles():
        return profiles.list()

    @app.post("/api/profiles")
    async def create_profile(request: Request):
        body = await request.json()
        kind = body.get("preset")
        if kind:
            if kind not in PRESETS:
                raise HTTPException(400, f"unknown preset {kind}")
            from agent.presets import deep_merge, preset
            cfg = deep_merge(preset(kind), body.get("config", {}))
        else:
            cfg = body.get("config") or {}
        if body.get("name"):
            cfg["name"] = body["name"]
        if not kind:
            errs = validate_config(cfg)
            if errs:
                raise HTTPException(422, "; ".join(errs))
        return profiles.create(cfg, note=body.get("note", "created"))

    @app.get("/api/profiles/{pid}")
    def get_profile(pid: str, version: int | None = None):
        p = profiles.get(pid, version)
        if not p:
            raise HTTPException(404, "profile not found")
        return p

    @app.put("/api/profiles/{pid}")
    async def save_profile(pid: str, request: Request):
        body = await request.json()
        errs = validate_config(body.get("config"))
        if errs:
            raise HTTPException(422, "; ".join(errs))
        try:
            return profiles.save(pid, body["config"], note=body.get("note", "saved"))
        except KeyError:
            raise HTTPException(404, "profile not found")

    @app.delete("/api/profiles/{pid}")
    def delete_profile(pid: str):
        profiles.delete(pid)
        return {"ok": True}

    @app.get("/api/profiles/{pid}/versions")
    def versions(pid: str):
        return profiles.versions(pid)

    @app.post("/api/profiles/{pid}/rollback")
    async def rollback(pid: str, request: Request):
        body = await request.json()
        try:
            return profiles.rollback(pid, int(body["version"]))
        except KeyError:
            raise HTTPException(404, "version not found")

    @app.get("/api/profiles/{pid}/prompt")
    def prompt_preview(pid: str):
        from agent.brain import CallContext
        p = profiles.get(pid)
        if not p:
            raise HTTPException(404, "profile not found")
        ctx = CallContext(call_id="preview", profile=p["config"])
        kb = app.state.knowledge.context_for(p["config"]) if app.state.knowledge else {}
        ctx.brief, ctx.kb_text = kb.get("brief"), kb.get("kb_text")
        return {"system_prompt": ctx.system_prompt(), "chars": len(ctx.system_prompt())}

    # ---- voices (M6 extends: preview, add clip, personas)
    @app.get("/api/voices")
    def voices(lang: str | None = None):
        from api.voices import voice_status
        cat = st.voices()
        return [{**{k: v.get(k) for k in ("id", "language", "engine", "display_name", "persona_tag", "license", "source")},
                 "demo_only": bool(v.get("demo_only")), "unrated": bool(v.get("unrated")), "status": voice_status(v),
                 "user_added": v["id"].startswith("user_")} for v in cat.list(lang)]

    # ---- calls / logs
    @app.get("/api/calls")
    def calls(limit: int = 50):
        rows = st.db.all("SELECT c.*, (SELECT COUNT(*) FROM turns t WHERE t.call_id=c.id) AS turns, "
                         "(SELECT COUNT(*) FROM guardrail_events g WHERE g.call_id=c.id) AS guard_events "
                         "FROM calls c ORDER BY started_at DESC LIMIT ?", (limit,))
        for r in rows:
            r["active"] = r["id"] in st.active_calls
        return rows

    @app.get("/api/calls/{cid}")
    def call_detail(cid: str):
        c = st.db.one("SELECT * FROM calls WHERE id=?", (cid,))
        if not c:
            raise HTTPException(404, "call not found")
        turns = st.db.all("SELECT * FROM turns WHERE call_id=? ORDER BY id", (cid,))
        for t in turns:
            for k in ("engine_json", "sources_json", "guardrail_json"):
                t[k.removesuffix("_json")] = json.loads(t.pop(k) or "null")
        guards = st.db.all("SELECT * FROM guardrail_events WHERE call_id=? ORDER BY id", (cid,))
        return {"call": c, "turns": turns, "guardrail_events": guards}
