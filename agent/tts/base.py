"""TTS interface. Engines are selected per language + voice by config and loaded on demand."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Voice:
    id: str
    language: str
    engine: str
    display_name: str
    license: str
    demo_only: bool = False
    params: dict = field(default_factory=dict)  # engine-specific (speaker description, ref clip, voice name)


@dataclass
class Synthesis:
    audio: np.ndarray  # mono float32
    sample_rate: int
    meta: dict = field(default_factory=dict)


class TTS(ABC):
    name: str = "base"
    languages: tuple[str, ...] = ()
    license: str = ""
    demo_only: bool = False
    streaming: bool = False  # True only if the engine emits audio before the full utterance

    def __init__(self, **options):
        self.options = options
        self._loaded = False

    @abstractmethod
    def load(self) -> None: ...

    def unload(self) -> None:
        self._loaded = False

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()
            self._loaded = True

    @abstractmethod
    def synthesize(self, text: str, voice: Voice) -> Synthesis: ...


def device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"
