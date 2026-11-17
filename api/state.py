"""Application state: config, DB, secrets, spend, engines, voices, active calls."""
from __future__ import annotations

import ipaddress
import uuid

from fastapi import HTTPException, Request

from agent.engines import EngineManager
from agent.llm.provider import AnthropicProvider, DemoProvider, FakeProvider, LLMProvider
from agent.logscrub import register_secret
from agent.voices import VoiceCatalog
from api.config import Config, load_config
from api.db import DB, dumps, now
from api.secrets_store import SecretStore
from api.spend import Spend, SpendCapReached


class AppState:
    def __init__(self, cfg: Config | None = None, provider_override: LLMProvider | None = None):
        self.cfg = cfg or load_config()
        self.db = DB(self.cfg.data_dir / "shaon.sqlite3")
        self.secrets = SecretStore(self.db, self.cfg.data_dir)
        self.spend = Spend(self.db, self.cfg.default_spend_cap_usd)
        self.engines = EngineManager()
        self.provider_override = provider_override
        self.active_calls: dict[str, dict] = {}
        self._provider_cache: tuple[str | None, LLMProvider] | None = None
        key, _ = self.secrets.api_key()
        register_secret(key)

    def voices(self) -> VoiceCatalog:
        rows = self.db.all("SELECT * FROM voices")
        extra = []
        for r in rows:
            import json
            extra.append({**r, "params": json.loads(r.get("params_json") or "{}"), "demo_only": bool(r["demo_only"])})
        return VoiceCatalog(extra)

    # ---- LLM provider resolution: override (tests) > fake (env) > key from Settings DB > .env > demo
    def provider(self) -> LLMProvider:
        if self.provider_override:
            return self.provider_override
        if self.cfg.llm_provider == "fake":
            return FakeProvider()
        key, _ = self.secrets.api_key()
        if not key:
            return DemoProvider()
        if self._provider_cache and self._provider_cache[0] == key:
            return self._provider_cache[1]
        p = AnthropicProvider(key, self.cfg.llm_model, spend=self.spend)
        self._provider_cache = (key, p)
        return p

    def health(self) -> dict:
        prov = self.provider()
        key, source = self.secrets.api_key()
        st = self.engines.status()
        reasons, notes = [], []
        if prov.name == "fake":
            reasons.append("FAKE language model active (test mode, SHAON_LLM_PROVIDER=fake): replies are scripted")
        elif prov.name == "demo":
            reasons.append("no Anthropic API key: add one in Settings (replies are a fixed demo-mode notice)")
        try:
            self.spend.check()
        except SpendCapReached:
            reasons.append("spend cap reached: raise it in Settings")
        eng = st["engines"]
        if not eng["faster-whisper"]["installed"] and not eng["indicconformer"]["installed"]:
            reasons.append("no STT engine installed")
        if not any(eng[e]["installed"] for e in ("kokoro", "indic-parler", "omnivoice")):
            reasons.append("no TTS engine installed")
        if not st["cuda"]:
            notes.append("No CUDA GPU: CPU profile. en/ja: Whisper small + Kokoro. hi/bn/kn: MMS STT + MMS/Kokoro voices "
                         "(MMS = CC-BY-NC, DEMO ONLY, robotic pipeline-testing voices). Product voices need the GPU engines (PENDING).")
        for e, v in eng.items():
            if v.get("pending"):
                notes.append(f"{e}: PENDING - {v['pending']}")
        return {"mode": "demo" if reasons else "full", "reasons": reasons, "notes": notes, "provider": prov.name,
                "key_present": bool(key), "key_source": source, "spend": self.spend.summary(), "cuda": st["cuda"],
                "engines": eng, "transport": self.cfg.transport, "exposed": self.cfg.exposed,
                "auth_required": bool(self.cfg.admin_password)}

    # ---- readiness per language (Get-ready screen, launcher status)
    def readiness(self) -> dict:
        from agent.engines import installed
        import statistics
        langs = ["en", "ja", "hi", "bn", "kn"]
        out = {}
        cat = self.voices()
        for lang in langs:
            name, opts, skipped = self.engines.stt_route(lang)
            stt = self.engines.peek_stt(name, opts)
            warm = stt is not None and stt._loaded and (name, lang) in self.engines.warmed
            stt_state = "ready" if warm else ("loading" if installed(name) else "unavailable")
            vids = [self.engines.cfg.get("default_voices", {}).get(lang)]
            fb = self.engines.cfg.get("cpu_fallback_voices", {}).get(lang) or []
            vids += [fb] if isinstance(fb, str) else fb
            voice, tts_state = None, "unavailable"
            for vid in [v for v in vids if v]:
                v = cat.voice(vid)
                if not v or not installed(v.engine) or v.engine in self.engines.load_errors:
                    continue
                voice = v
                tts_state = "ready" if self.engines.tts_ready(v.engine, lang) else "loading"
                if v.engine not in ("indic-parler", "omnivoice") or tts_state == "ready":
                    break
            states = {stt_state, tts_state}
            state = "unavailable" if "unavailable" in states else ("loading" if "loading" in states else "ready")
            fa = [r["first_audio_ms"] for r in self.db.all(
                "SELECT first_audio_ms FROM turns WHERE role='agent' AND language=? AND first_audio_ms IS NOT NULL ORDER BY id DESC LIMIT 20", (lang,))]
            out[lang] = {"state": state, "stt": name, "stt_state": stt_state, "tts_voice": voice.id if voice else None,
                         "tts_engine": voice.engine if voice else None, "tts_state": tts_state,
                         "robotic": bool(voice and voice.engine == "mms-tts"), "demo_only": bool(voice and voice.demo_only),
                         "first_audio_median_ms": round(statistics.median(fa)) if fa else None, "first_audio_n": len(fa)}
        prov = self.provider()
        return {"languages": out, "cuda": self.engines.cuda, "provider": prov.name, "real_llm": prov.is_real,
                "active_calls": len(self.active_calls), "max_calls": self.cfg.max_calls,
                "max_call_seconds": self.cfg.max_call_seconds, "busy": len(self.active_calls) >= self.cfg.max_calls}

    # ---- calls / turns logging
    def new_call(self, profile_id: str | None, version_id: int | None, transport: str) -> str:
        cid = "call_" + uuid.uuid4().hex[:12]
        self.db.execute("INSERT INTO calls(id,profile_id,profile_version_id,transport,started_at,provider) VALUES(?,?,?,?,?,?)",
                        (cid, profile_id, version_id, transport, now(), self.provider().name))
        return cid

    def log_turn(self, call_id: str, row: dict) -> int:
        cols = ["role", "language", "text", "stt_ms", "llm_ms", "llm_ttft_ms", "guard_ms", "tts_ms", "first_audio_ms",
                "lang_reason", "engine_json", "sources_json", "guardrail_json"]
        vals = [row.get(c) if not c.endswith("_json") else (dumps(row[c]) if row.get(c) is not None else None) for c in cols]
        from agent.logscrub import scrub
        vals[2] = scrub(vals[2] or "")
        return self.db.execute(f"INSERT INTO turns(call_id,{','.join(cols)},created_at) VALUES(?,{','.join('?' * len(cols))},?)",
                               (call_id, *vals, now()))

    def update_turn(self, turn_id: int, fields: dict) -> None:
        if not turn_id or not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE turns SET {sets} WHERE id=?", (*fields.values(), turn_id))

    def log_guard(self, call_id: str, v) -> None:
        d = v.__dict__ if hasattr(v, "__dict__") else dict(v)
        self.db.execute("INSERT INTO guardrail_events(call_id,stage,verdict,rule,detail,created_at) VALUES(?,?,?,?,?,?)",
                        (call_id, d.get("stage"), d.get("action"), d.get("rule"), d.get("detail"), now()))

    def end_call(self, call_id: str, info: dict) -> None:
        self.db.execute("UPDATE calls SET ended_at=?, languages_used=?, end_reason=? WHERE id=?",
                        (now(), ",".join(info.get("languages_used", [])), info.get("end_reason"), call_id))
        self.active_calls.pop(call_id, None)


def is_loopback(request: Request) -> bool:
    # behind the Quick Tunnel every visitor's TCP peer is 127.0.0.1: forwarded requests are NEVER "this machine"
    from api.auth import has_forwarding_headers
    if has_forwarding_headers(request.headers):
        return False
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("localhost", "testclient")


def require_admin(state: AppState, request: Request, for_key: bool = False) -> None:
    """Editing secrets/caps: needs ADMIN_PASSWORD if set; otherwise only from this machine and not when exposed."""
    if for_key and not state.cfg.allow_key_edit:
        raise HTTPException(403, "Key editing is disabled on this deployment (ALLOW_KEY_EDIT=false).")
    pw = state.cfg.admin_password
    if pw:
        import hmac

        auth = getattr(request.app.state, "auth", None)
        if auth is not None and auth.role_of_token(auth.token_from(request)) == "admin":
            return
        given = request.headers.get("x-admin-password", "")
        if not hmac.compare_digest(given.encode(), pw.encode()):
            raise HTTPException(401, "Admin password required.")
        return
    if state.cfg.exposed or not is_loopback(request):
        raise HTTPException(403, "Set ADMIN_PASSWORD to edit settings remotely.")
