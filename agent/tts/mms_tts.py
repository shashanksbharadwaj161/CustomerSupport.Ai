"""facebook/mms-tts-{hin,ben,kan} (VITS) via transformers VitsModel.

LICENSE: CC-BY-NC-4.0 (non-commercial): DEMO ONLY. Honest label: robotic, PIPELINE-TESTING voices so Bengali and
Kannada calls can be exercised on a CPU. Not product voices and not rated by native speakers.
"""
from __future__ import annotations

import threading

import numpy as np

from agent.tts.base import TTS, Synthesis, Voice

ISO3 = {"hi": "hin", "bn": "ben", "kn": "kan"}


class MMSTTS(TTS):
    name = "mms-tts"
    languages = ("hi", "bn", "kn")
    license = "CC-BY-NC-4.0 (DEMO ONLY)"
    demo_only = True

    def load(self) -> None:
        import torch

        self.torch = torch
        self.models: dict[str, tuple] = {}
        self._lock = threading.Lock()

    def _get(self, lang: str):
        if lang not in self.models:
            from transformers import AutoTokenizer, VitsModel

            repo = f"facebook/mms-tts-{ISO3[lang]}"
            self.models[lang] = (VitsModel.from_pretrained(repo).eval(), AutoTokenizer.from_pretrained(repo))
        return self.models[lang]

    def synthesize(self, text: str, voice: Voice) -> Synthesis:
        self.ensure_loaded()
        with self._lock:
            model, tok = self._get(voice.language)
            inputs = tok(text, return_tensors="pt")
            if inputs["input_ids"].shape[-1] == 0:
                raise ValueError("MMS tokenizer produced no tokens for this text")
            self.torch.manual_seed(int(voice.params.get("seed", 0)))  # VITS is stochastic: fixed seed = repeatable
            with self.torch.inference_mode():
                wav = model(**inputs).waveform[0].cpu().numpy().astype(np.float32)
        return Synthesis(wav, model.config.sampling_rate, meta={"demo_only": True})
