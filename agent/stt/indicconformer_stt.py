"""AI4Bharat IndicConformer 600M multilingual (MIT, gated on Hugging Face: accept terms + HF_TOKEN).

Loaded through transformers with trust_remote_code, per the model card
(https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual). This path does not
need the NeMo fork that the GitHub monolingual checkpoints need. trust_remote_code runs
code from the model repo: pin a revision (option `revision`) once M0 picks one.
"""
from __future__ import annotations

import numpy as np

from agent.stt.base import STT, Transcript


class IndicConformerSTT(STT):
    name = "indicconformer"
    languages = ("hi", "bn", "kn")

    def load(self) -> None:
        import torch
        from transformers import AutoModel

        self.torch = torch
        self.model = AutoModel.from_pretrained(
            self.options.get("model", "ai4bharat/indic-conformer-600m-multilingual"),
            trust_remote_code=True, revision=self.options.get("revision"))
        self.decoding = self.options.get("decoding", "rnnt")  # "ctc" | "rnnt", compared in M0

    def transcribe(self, audio: np.ndarray, language: str | None) -> Transcript:
        if language not in self.languages:
            raise ValueError(f"IndicConformer needs one of {self.languages}, got {language!r}")
        self.ensure_loaded()
        wav = self.torch.from_numpy(audio).unsqueeze(0)
        out = self.model(wav, language, self.decoding)
        text = out if isinstance(out, str) else str(out[0] if isinstance(out, (list, tuple)) else out)
        return Transcript(text=text.strip(), language=language, meta={"decoding": self.decoding})
