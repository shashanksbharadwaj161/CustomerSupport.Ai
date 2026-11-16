"""facebook/mms-1b-all (Wav2Vec2 CTC + per-language adapters).

LICENSE: CC-BY-NC-4.0 (non-commercial). EVALUATION / DEMO ONLY - never ship in a product.
Used as a CPU candidate for Hindi (hin), Bengali (ben), Kannada (kan). ~3.9 GB of fp32 weights; one adapter swap per language.
"""
from __future__ import annotations

import threading

import numpy as np

from agent.stt.base import STT, Transcript

ISO3 = {"hi": "hin", "bn": "ben", "kn": "kan", "en": "eng", "ja": "jpn"}


class MMSSTT(STT):
    name = "mms"
    languages = ("hi", "bn", "kn")
    license = "CC-BY-NC-4.0 (evaluation/demo only)"
    demo_only = True

    def load(self) -> None:
        import torch
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        repo = self.options.get("model", "facebook/mms-1b-all")
        self.torch = torch
        torch.set_num_threads(max(1, torch.get_num_threads()))
        self.processor = AutoProcessor.from_pretrained(repo)
        self.model = Wav2Vec2ForCTC.from_pretrained(repo)
        self.model.eval()
        self._lang = None
        self._lock = threading.Lock()

    def _set_lang(self, lang: str) -> None:
        iso = ISO3[lang]
        if self._lang != iso:
            self.processor.tokenizer.set_target_lang(iso)
            self.model.load_adapter(iso)
            self._lang = iso

    def transcribe(self, audio: np.ndarray, language: str | None) -> Transcript:
        if language not in self.languages:
            raise ValueError(f"MMS adapter configured for {self.languages}, got {language!r}")
        self.ensure_loaded()
        with self._lock:  # adapter swap + forward must not interleave
            self._set_lang(language)
            inputs = self.processor(audio, sampling_rate=16000, return_tensors="pt")
            with self.torch.inference_mode():
                logits = self.model(**inputs).logits
            ids = self.torch.argmax(logits, dim=-1)[0]
            text = self.processor.decode(ids)
        return Transcript(text=text.strip(), language=language, meta={"adapter": ISO3[language]})
