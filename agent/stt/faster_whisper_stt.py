"""faster-whisper (MIT). Used for ja/en STT, Hindi fallback, and language ID."""
from __future__ import annotations

import numpy as np

from agent.stt.base import STT, Transcript


class FasterWhisperSTT(STT):
    name = "faster-whisper"
    languages = ("en", "ja", "hi", "bn", "kn")
    supports_lid = True

    def load(self) -> None:
        import torch  # noqa: F401  (optional; only to pick device)
        from faster_whisper import WhisperModel

        model = self.options.get("model", "large-v3")
        device = self.options.get("device") or ("cuda" if _cuda() else "cpu")
        compute = self.options.get("compute_type") or ("float16" if device == "cuda" else "int8")
        self.model = WhisperModel(model, device=device, compute_type=compute,
                                  download_root=self.options.get("download_root"))

    def _kw(self) -> dict:
        # beam_size / temperature come from engines.json options. CPU profile: greedy (beam 1) with NO temperature-fallback
        # retries: on CPU the retries made Kannada/Bengali clips take ~1.6 min each (measured). GPU profile: beam 5 + fallback.
        temp = self.options.get("temperature")
        kw = {"beam_size": self.options.get("beam_size", 5), "vad_filter": False, "condition_on_previous_text": False}
        if temp is not None:
            kw["temperature"] = temp
        return kw

    def transcribe(self, audio: np.ndarray, language: str | None) -> Transcript:
        self.ensure_loaded()
        segments, info = self.model.transcribe(audio, language=language, **self._kw())
        text = " ".join(s.text.strip() for s in segments).strip()
        probs = dict(info.all_language_probs or []) if language is None else {}
        return Transcript(text=text, language=info.language, lid_probs=probs,
                          meta={"language_probability": info.language_probability})

    def detect_language(self, audio: np.ndarray) -> dict[str, float]:
        """Language probabilities from ONE encoder pass. transcribe() detects before its lazy segment generator runs, so
        nothing is decoded here; the generator is kept (per thread) so take_pending() can decode the same audio in the
        detected language WITHOUT a second encoder pass (measured: the double pass cost ~1.4-2 s per en/ja turn on CPU)."""
        self.ensure_loaded()
        segments, info = self.model.transcribe(audio, language=None, **self._kw())
        self._tls().pending = (id(audio), info.language, segments)
        return dict(info.all_language_probs or [])

    def take_pending(self, audio: np.ndarray, language: str) -> str | None:
        """Decode the audio passed to the last detect_language() call if `language` is the language it detected."""
        pend = getattr(self._tls(), "pending", None)
        self._tls().pending = None
        if not pend or pend[0] != id(audio) or pend[1] != language:
            return None
        return " ".join(s.text.strip() for s in pend[2]).strip()

    def _tls(self):
        import threading
        if not hasattr(self, "_local"):
            self._local = threading.local()
        return self._local


def _cuda() -> bool:
    import os
    if (os.environ.get("SHAON_DEVICE") or "").lower() == "cpu":
        return False
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False
