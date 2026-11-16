"""TTS registry: engine name -> class. Import is lazy so unused engines need no deps."""
from __future__ import annotations

from agent.tts.base import TTS, Synthesis, Voice  # noqa: F401

_REGISTRY = {
    "omnivoice": ("agent.tts.omnivoice_tts", "OmniVoiceTTS"),  # DEMO ONLY (CC-BY-NC weights)
    "indic-parler": ("agent.tts.parler_tts", "IndicParlerTTS"),
    "kokoro": ("agent.tts.kokoro_tts", "KokoroTTS"),
}


def available() -> list[str]:
    return list(_REGISTRY)


def create(name: str, **options) -> TTS:
    import importlib

    mod, cls = _REGISTRY[name]
    return getattr(importlib.import_module(mod), cls)(**options)
