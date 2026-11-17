"""Engine manager: per-language STT/TTS selection, lazy loading, shared cached instances, honest status.

Verification status is static and conservative: an engine is 'verified_here' only if it ran end to end
in this repository's tests. Everything else is 'pending' until the user runs M0 on a GPU / Kaggle.
"""
from __future__ import annotations

import importlib.util
import json
import threading

from agent import stt as stt_registry
from agent import tts as tts_registry
import pathlib

ENGINES_JSON = pathlib.Path(__file__).resolve().parent / "engines.json"

ENGINE_INFO = {
    "faster-whisper": {"kind": "stt", "module": "faster_whisper", "license": "MIT", "demo_only": False,
                       "verified_here": "en, ja on CPU (Whisper small): E2E browser test",
                       "repo": "Systran/faster-whisper-small"},
    "indicconformer": {"kind": "stt", "module": "transformers", "license": "MIT (gated)", "demo_only": False,
                       "verified_here": None, "repo": "ai4bharat/indic-conformer-600m-multilingual",
                       "pending": "Needs HF token + GPU run (M0). Adapter complete, never run here."},
    "mms": {"kind": "stt", "module": "transformers", "license": "CC-BY-NC-4.0: evaluation/demo only", "demo_only": True,
            "verified_here": "hi, bn, kn on CPU: FLEURS eval + browser E2E", "repo": "facebook/mms-1b-all"},
    "mms-tts": {"kind": "tts", "module": "transformers", "license": "CC-BY-NC-4.0: DEMO ONLY (robotic pipeline-testing voices)",
                "demo_only": True, "verified_here": "hi, bn, kn on CPU: synthesis + round-trip proxy + browser E2E",
                "repo": "facebook/mms-tts-ben"},
    "kokoro": {"kind": "tts", "module": "kokoro", "license": "Apache-2.0", "demo_only": False,
               "verified_here": "en, ja on CPU: E2E browser test (Hindi voices: unrated)", "repo": "hexgrad/Kokoro-82M"},
    "indic-parler": {"kind": "tts", "module": "parler_tts", "license": "Apache-2.0 (gated)", "demo_only": False,
                     "verified_here": None, "repo": "ai4bharat/indic-parler-tts",
                     "pending": "Needs HF token + GPU run + native ratings (M0). Adapter complete, never run here."},
    "omnivoice": {"kind": "tts", "module": "omnivoice", "license": "weights CC-BY-NC: DEMO ONLY", "demo_only": True,
                  "verified_here": None, "repo": "k2-fsa/OmniVoice",
                  "pending": "Needs GPU run + native ratings (M0). Adapter complete, never run here."},
}


def load_engines_config() -> dict:
    return json.loads(ENGINES_JSON.read_text(encoding="utf-8"))


def has_cuda() -> bool:
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return True
    except Exception:
        pass
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def installed(engine: str) -> bool:
    mod = ENGINE_INFO[engine]["module"]
    return importlib.util.find_spec(mod) is not None


def weights_cached(repo: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        for f in ("config.json", "model.bin", "README.md"):
            r = try_to_load_from_cache(repo, f)
            if isinstance(r, str):
                return True
    except Exception:
        pass
    return False


def _hf_token() -> bool:
    import os
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return True
    try:
        from huggingface_hub import get_token
        return bool(get_token())
    except Exception:
        return False


class EngineManager:
    def __init__(self):
        self.cfg = load_engines_config()
        self.cuda = has_cuda()
        self._stt: dict[str, object] = {}
        self._tts: dict[str, object] = {}
        self._lock = threading.Lock()
        self.load_errors: dict[str, str] = {}
        self.warmed: set[tuple[str, str]] = set()  # (engine, lang) that completed a real transcription

    def stt_candidates(self, lang: str) -> list[tuple[str, dict]]:
        """Ordered STT candidates for a language from engines.json ('stt' on CUDA, 'stt_cpu' otherwise).
        An entry is either {"engine", "options"} or {"order": [{"engine", "options"}, ...]}. Whisper is always the last resort."""
        table = self.cfg["stt"] if self.cuda else self.cfg.get("stt_cpu", self.cfg["stt"])
        entry = table.get(lang) or table["en"]
        order = entry.get("order") or [entry]
        cands = [(c["engine"], dict(c.get("options", {}))) for c in order]
        if not any(n == "faster-whisper" for n, _ in cands):
            cands.append(("faster-whisper", {"model": "small"}))
        return cands

    def usable(self, name: str) -> tuple[bool, str]:
        if name not in ENGINE_INFO:
            return False, "unknown engine"
        if not installed(name):
            return False, "not installed"
        if name in self.load_errors:
            return False, "load error: " + self.load_errors[name][:80]
        if name == "indicconformer" and not weights_cached(ENGINE_INFO[name]["repo"]) and not _hf_token():
            return False, "gated weights not downloaded and no HF token"
        return True, "ok"

    def stt_route(self, lang: str) -> tuple[str, dict, list[str]]:
        """First usable candidate + the reasons the earlier ones were skipped (logged per turn)."""
        skipped = []
        for name, opts in self.stt_candidates(lang):
            ok, why = self.usable(name)
            if ok:
                return name, opts, skipped
            skipped.append(f"{name}: {why}")
        return "faster-whisper", {"model": "small"}, skipped

    def stt_choice(self, lang: str) -> tuple[str, dict]:
        name, opts, _ = self.stt_route(lang)
        return name, opts

    def get_stt(self, name: str, opts: dict):
        key = name + json.dumps(opts, sort_keys=True)
        with self._lock:
            if key not in self._stt:
                self._stt[key] = stt_registry.create(name, **opts)
            eng = self._stt[key]
        try:
            eng.ensure_loaded()
        except Exception as e:
            self.load_errors[name] = f"{type(e).__name__}: {e}"[:300]
            raise
        return eng

    def warm_stt(self, lang: str) -> None:
        """Load AND exercise the STT a call would use for `lang` (1 s of silence): loads per-language adapters
        (MMS) and first-run kernels, so the first caller does not pay ~100 s (measured on CPU before this existed)."""
        import numpy as np
        name, opts, _ = self.stt_route(lang)
        eng = self.get_stt(name, opts)
        eng.transcribe(np.zeros(16000, dtype=np.float32), lang)
        self.warmed.add((name, lang))

    def peek_stt(self, name: str, opts: dict):
        """Existing engine instance (no loading) or None."""
        return self._stt.get(name + json.dumps(opts, sort_keys=True))

    def tts_ready(self, name: str, lang: str) -> bool:
        eng = self._tts.get(name)
        if eng is None or not eng._loaded:
            return False
        models = getattr(eng, "models", None)  # per-language model engines (MMS-TTS)
        if isinstance(models, dict):
            return lang in models
        pipes = getattr(eng, "pipelines", None)  # Kokoro: one pipeline per language
        if isinstance(pipes, dict) and name == "kokoro":
            return {"en": "a", "ja": "j", "hi": "h"}.get(lang) in pipes or lang in pipes
        return True

    def lid_engine(self):
        name, opts = self.stt_choice("en") if self.stt_choice("en")[0] == "faster-whisper" else ("faster-whisper", {"model": "small"})
        return self.get_stt(name, opts)

    def get_tts(self, name: str):
        with self._lock:
            if name not in self._tts:
                self._tts[name] = tts_registry.create(name)
            eng = self._tts[name]
        try:
            eng.ensure_loaded()
        except Exception as e:
            self.load_errors[name] = f"{type(e).__name__}: {e}"[:300]
            raise
        return eng

    def status(self) -> dict:
        out = {}
        for name, info in ENGINE_INFO.items():
            inst = installed(name)
            out[name] = {
                "kind": info["kind"], "license": info["license"], "demo_only": info["demo_only"],
                "installed": inst, "weights_cached": weights_cached(info["repo"]) if inst else False,
                "loaded": any(k.startswith(name) for k in self._stt) or name in self._tts,
                "verified_here": info.get("verified_here"), "pending": info.get("pending"),
                "load_error": self.load_errors.get(name),
            }
        return {"cuda": self.cuda, "engines": out}
