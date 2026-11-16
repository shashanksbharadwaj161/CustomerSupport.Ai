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

    def transcribe(self, audio: np.ndarray, language: str | None) -> Transcript:
        self.ensure_loaded()
        segments, info = self.model.transcribe(
            audio, language=language, beam_size=self.options.get("beam_size", 5),
            vad_filter=False, condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments).strip()
        probs = dict(info.all_language_probs or []) if language is None else {}
        return Transcript(text=text, language=info.language, lid_probs=probs,
                          meta={"language_probability": info.language_probability})

    def detect_language(self, audio: np.ndarray) -> dict[str, float]:
        self.ensure_loaded()
        # transcribe() computes language info before the lazy segment generator runs,
        # so not iterating segments keeps this to the detection pass only.
        _segments, info = self.model.transcribe(audio, language=None)
        return dict(info.all_language_probs or [])


def _cuda() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False
