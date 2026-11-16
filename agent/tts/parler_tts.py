"""AI4Bharat Indic Parler-TTS (Apache-2.0, gated on HF). Product track for bn/hi/kn (and Indian English).

Voice = named speaker inside a text description, e.g. "Divya's voice is ... very close recording."
"""
from __future__ import annotations

import numpy as np

from agent.tts.base import TTS, Synthesis, Voice, device


class IndicParlerTTS(TTS):
    name = "indic-parler"
    languages = ("hi", "bn", "kn", "en")
    license = "Apache-2.0"

    def load(self) -> None:
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        repo = self.options.get("model", "ai4bharat/indic-parler-tts")
        self.dev = self.options.get("device") or device()
        self.torch = torch
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(repo).to(self.dev)
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.desc_tok = AutoTokenizer.from_pretrained(self.model.config.text_encoder._name_or_path)

    def synthesize(self, text: str, voice: Voice) -> Synthesis:
        self.ensure_loaded()
        desc = voice.params["description"]
        d = self.desc_tok(desc, return_tensors="pt").to(self.dev)
        t = self.tok(text, return_tensors="pt").to(self.dev)
        with self.torch.inference_mode():
            out = self.model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                                      prompt_input_ids=t.input_ids,
                                      prompt_attention_mask=t.attention_mask)
        wav = out.cpu().numpy().squeeze().astype(np.float32)
        return Synthesis(wav, self.model.config.sampling_rate)
