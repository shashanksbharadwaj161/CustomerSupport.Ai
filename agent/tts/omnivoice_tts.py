"""OmniVoice (k2-fsa).

DEMO ONLY: code is Apache-2.0 but the WEIGHTS ARE CC-BY-NC (non-commercial).
Never ship this engine in a product. Every voice from it carries demo_only=True and a UI badge.
Voice cloning only from consenting speakers or model-generated reference clips.
No documented streaming: audio is returned only after the full utterance.
"""
from __future__ import annotations

import numpy as np

from agent.tts.base import TTS, Synthesis, Voice, device


class OmniVoiceTTS(TTS):
    name = "omnivoice"
    languages = ("en", "ja", "hi", "bn", "kn")
    license = "code Apache-2.0, weights CC-BY-NC (DEMO ONLY)"
    demo_only = True
    SAMPLE_RATE = 24000  # per README: generate() returns 24 kHz arrays

    def load(self) -> None:
        import torch
        from omnivoice import OmniVoice

        dev = self.options.get("device") or device()
        dtype = torch.float16 if dev.startswith("cuda") else torch.float32
        self.model = OmniVoice.from_pretrained(
            self.options.get("model", "k2-fsa/OmniVoice"), device_map=dev, dtype=dtype)

    def synthesize(self, text: str, voice: Voice) -> Synthesis:
        self.ensure_loaded()
        kw = {"text": text, "num_step": self.options.get("num_step", 32)}
        p = voice.params
        if p.get("ref_audio"):
            kw["ref_audio"] = p["ref_audio"]
            if p.get("ref_text"):
                kw["ref_text"] = p["ref_text"]  # stored with the clip (PLAN section 10)
        elif p.get("instruct"):
            # Voice design is trained on zh/en only: expect instability for other languages.
            kw["instruct"] = p["instruct"]
        audio = self.model.generate(**kw)
        return Synthesis(np.asarray(audio[0], dtype=np.float32), self.SAMPLE_RATE,
                         meta={"demo_only": True})
