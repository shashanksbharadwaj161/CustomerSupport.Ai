"""STT interface. Engines are selected per language by agent/engines.json and loaded on demand."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

SAMPLE_RATE = 16000


@dataclass
class Transcript:
    text: str
    language: str | None
    lid_probs: dict[str, float] = field(default_factory=dict)  # only if the engine does LID
    meta: dict = field(default_factory=dict)


class STT(ABC):
    name: str = "base"
    languages: tuple[str, ...] = ()
    supports_lid: bool = False

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
    def transcribe(self, audio: np.ndarray, language: str | None) -> Transcript:
        """audio: mono float32 at 16 kHz. language None means auto-detect (if supported)."""

    def detect_language(self, audio: np.ndarray) -> dict[str, float]:
        raise NotImplementedError(f"{self.name} does not do language ID")
