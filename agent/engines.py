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


class EngineManager:
    def __init__(self):
        self.cfg = load_engines_config()
        self.cuda = has_cuda()
        self._stt: dict[str, object] = {}
        self._tts: dict[str, object] = {}
        self._lock = threading.Lock()
        self.load_errors: dict[str, str] = {}

    def stt_choice(self, lang: str) -> tuple[str, dict]:
        table = self.cfg["stt"] if self.cuda else self.cfg.get("stt_cpu", self.cfg["stt"])
        c = table.get(lang) or table["en"]
        name, opts = c["engine"], dict(c.get("options", {}))
        if not installed(name) or name in self.load_errors:
            # honest fallback: Whisper with the target language (shown in turn metadata)
            fb = self.cfg.get("stt_cpu", {}).get(lang) or {"engine": "faster-whisper", "options": {"model": "small"}}
            name, opts = fb["engine"], dict(fb.get("options", {}))
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
