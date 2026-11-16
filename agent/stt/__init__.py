"""STT registry: engine name -> class. Import is lazy so unused engines need no deps."""
from __future__ import annotations

from agent.stt.base import STT, Transcript  # noqa: F401

_REGISTRY = {
    "faster-whisper": ("agent.stt.faster_whisper_stt", "FasterWhisperSTT"),
    "indicconformer": ("agent.stt.indicconformer_stt", "IndicConformerSTT"),
    "mms": ("agent.stt.mms_stt", "MMSSTT"),  # CC-BY-NC: evaluation/demo only
}


def available() -> list[str]:
    return list(_REGISTRY)


def create(name: str, **options) -> STT:
    import importlib

    mod, cls = _REGISTRY[name]
    return getattr(importlib.import_module(mod), cls)(**options)
