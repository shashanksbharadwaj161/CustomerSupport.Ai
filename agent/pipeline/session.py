"""Per-call session: language state, timings, engine access, DB logging hooks.

The API layer creates a CallSession with its dependencies (no import of api/ from agent/).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from agent.brain import CallContext, TurnEngine
from agent.engines import EngineManager
from agent.lang import LANGS, dominant_language
from agent.lang.routing import decide_language
from agent.voices import VoiceCatalog


@dataclass
class Hooks:
    """Callbacks into the app (DB, spend, guard, retrieval). All optional for tests."""
    provider: Callable[[], Any]
    model: str = "claude-haiku-5-5"
    guard: Any = None
    retriever: Any = None
    on_turn: Callable[[str, dict], int | None] = lambda call_id, row: None
    on_turn_update: Callable[[int, dict], None] = lambda turn_id, fields: None
    on_guard: Callable[[str, Any], None] = lambda call_id, verdict: None
    on_call_end: Callable[[str, dict], None] = lambda call_id, info: None


@dataclass
class CallSession:
    ctx: CallContext
    engines: EngineManager
    voices: VoiceCatalog
    hooks: Hooks
    transport: str = "smallwebrtc"
    languages_used: set = field(default_factory=set)
    t_user_stopped: float | None = None
    t_turn_tts_start: float | None = None
    pending_first_audio_turn: int | None = None
    tts_first_ms: int | None = None
    ensure_reference: Any = None  # callable(voice) for OmniVoice ref_from voices (set by the API layer)
    lid_threshold: float = 0.5
    lid_bias: float = 0.1
    script_override_max_conf: float = 0.6

    def __post_init__(self):
        lid = self.engines.cfg.get("lid", {})
        if isinstance(lid.get("threshold"), (int, float)):
            self.lid_threshold = float(lid["threshold"])
        if isinstance(lid.get("prev_bias"), (int, float)):
            self.lid_bias = float(lid["prev_bias"])
        if isinstance(lid.get("script_override_max_conf"), (int, float)):
            self.script_override_max_conf = float(lid["script_override_max_conf"])
        self.ctx.current_lang = self.ctx.profile["languages"]["default"]

    @property
    def enabled(self) -> list[str]:
        return [l for l in self.ctx.profile["languages"]["enabled"] if l in LANGS]

    def engine(self) -> TurnEngine:
        return TurnEngine(self.ctx, self.hooks.provider(), self.hooks.model, guard=self.hooks.guard,
                          retriever=self.hooks.retriever, log_guard=lambda v: self.hooks.on_guard(self.ctx.call_id, v))

    # ---- STT side (runs in a worker thread) ----
    def transcribe_turn(self, audio: np.ndarray) -> dict:
        t0 = time.perf_counter()
        enabled, prev = self.enabled, self.ctx.current_lang
        info: dict[str, Any] = {"lid_probs": None, "reason": None, "engines": []}
        if self.ctx.override_lang:
            lang, info["reason"] = self.ctx.override_lang, "override"
        elif len(enabled) == 1 or not self.ctx.profile["languages"].get("auto_switch", True):
            lang, info["reason"] = (enabled[0] if len(enabled) == 1 else prev), "single_language"
        else:
            lid = self.engines.lid_engine()
            tl = time.perf_counter()
            # detection only (encoder + one decoder step): no transcript is decoded here, so a language routed to a
            # different engine (MMS / IndicConformer) is transcribed exactly once (measured: ~3-6 s saved per Indic turn on CPU)
            raw = lid.detect_language(audio)
            info["lid_ms"] = round((time.perf_counter() - tl) * 1000)
            # renormalize over the agent's enabled languages: Whisper often puts Hindi mass on Urdu (measured: raw hi 0.47-0.51
            # on FLEURS clips that are 0.96 once restricted), which would wrongly look "unsure"
            probs = {k: v for k, v in raw.items() if k in enabled}
            total = sum(probs.values())
            if total > 0:
                probs = {k: v / total for k, v in probs.items()}
            info["lid_probs"] = {k: round(v, 3) for k, v in probs.items()}
            first = None
            if max(probs.values(), default=0.0) < self.script_override_max_conf:
                # unsure: also decode the auto-language transcript so the SCRIPT can break the tie (rare on FLEURS)
                first = lid.transcribe(audio, None)
                info["lid_text"] = first.text
                info["lid_ms"] = round((time.perf_counter() - tl) * 1000)
            d = decide_language(probs, first.text if first else None, prev, default_lang=prev, threshold=self.lid_threshold,
                                prev_bias=self.lid_bias, script_override_max_conf=self.script_override_max_conf)
            lang, info["reason"] = d.language, d.reason
            if d.reason == "low_conf_keep_prev" and probs:
                top = max(probs, key=probs.get)
                if top != prev:  # PLAN 6.2: run both recognizers, keep the transcript whose script fits
                    a = self._stt(audio, prev, info)
                    b = self._stt(audio, top, info)
                    fit_b = dominant_language(b)[0] == top and top != "en"
                    lang, text = (top, b) if fit_b else (prev, a)
                    info["reason"] = "dual_recognition"
                    return self._finish(text, lang, info, t0)
            if first is not None and first.language == lang and self._same_engine(lid, lang):
                info["engines"].append(f"faster-whisper:{lid.options.get('model', '')}:{lang}:reused")
                return self._post_script_check(audio, first.text, lang, info, t0, enabled)
        text = self._stt(audio, lang, info)
        return self._post_script_check(audio, text, lang, info, t0, enabled)

    def _post_script_check(self, audio, text, lang, info, t0, enabled) -> dict:
        conf = max((info.get("lid_probs") or {}).values(), default=0.0)
        if info["reason"] not in ("override", "single_language") and conf < self.script_override_max_conf:
            d2 = decide_language(None, text, lang, default_lang=lang, threshold=1.1)
            if d2.reason == "script_flip" and d2.language in enabled and d2.language != lang:
                lang, info["reason"] = d2.language, "script_flip"
                text = self._stt(audio, lang, info)
        return self._finish(text, lang, info, t0)

    def _same_engine(self, lid, lang: str) -> bool:
        name, opts = self.engines.stt_choice(lang)
        return name == "faster-whisper" and opts.get("model") == lid.options.get("model")

    def _stt(self, audio, lang, info) -> str:
        """Route to the first usable STT for the language; on a load/run failure fall through the configured order
        IN THE SAME TURN. Every skip and fallback is recorded in info (sent to the client and stored per turn)."""
        name, opts, skipped = self.engines.stt_route(lang)
        if skipped:
            info.setdefault("routing", []).extend(f"{lang}: skipped {s}" for s in skipped)
        while True:
            try:
                eng = self.engines.get_stt(name, opts)
                text = eng.transcribe(audio, lang).text
                break
            except Exception as e:
                if name == "faster-whisper":
                    raise
                self.engines.load_errors[name] = f"{type(e).__name__}: {e}"[:300]
                info.setdefault("fallbacks", []).append(f"{name} failed ({type(e).__name__}): next in order")
                name, opts, _ = self.engines.stt_route(lang)
        info["engines"].append(f"{name}:{opts.get('model') or opts.get('decoding') or ''}:{lang}")
        if hasattr(self.engines, "warmed"):
            self.engines.warmed.add((name, lang))
        return text

    def _finish(self, text, lang, info, t0) -> dict:
        info.setdefault("lid_text", text)
        info.update(text=text.strip(), lang=lang, stt_ms=round((time.perf_counter() - t0) * 1000))
        if text.strip():
            self.ctx.current_lang = lang
            self.languages_used.add(lang)
        return info

    # ---- TTS side ----
    def voice_for(self, lang: str):
        vid = self.ctx.voice_by_lang.get(lang) or self.engines.cfg.get("default_voices", {}).get(lang)
        v = self.voices.voice(vid) if vid else None
        return v

    def fallback_voices(self, lang: str) -> list:
        ids = self.engines.cfg.get("cpu_fallback_voices", {}).get(lang) or []
        ids = [ids] if isinstance(ids, str) else ids
        return [v for v in (self.voices.voice(i) for i in ids) if v]

    def fallback_voice(self, lang: str):
        vs = self.fallback_voices(lang)
        return vs[0] if vs else None
