"""Mithi v2 Flash (Oomni/mithi-v2-flash, Apache-2.0): 99M-parameter TTS for 11 Indian languages + English, 10 voices,
24 kHz, runs on CPU. Used here for Hindi, Bengali and Kannada (and available for English).

The model ships as a self-contained `run.py` (its modules are embedded as source strings and loaded by an import hook
that only answers `mithi_tts.*` names). I reviewed it before use: no network access, no subprocess, no pickle; weights
are safetensors. We load that file from the LOCAL Hugging Face cache only (scripts/fetch_models.py downloads it; the
adapter never downloads during a call).

Honest limits (from the author's model card, not re-measured by listeners here): flatter intonation than natural speech,
Kannada can sound faster than natural, no published human listening study (MOS). Our measurements (CPU, 4 threads,
round-trip recognition) are in eval/results.md.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading

import numpy as np

from agent.tts.base import TTS, Synthesis, Voice

REPO = "Oomni/mithi-v2-flash"
SR = 24000
PEAK = 0.85  # Mithi's raw output peaks around 0.25: normalise so it is as loud as the Kokoro voices


def model_dir() -> str:
    """Local snapshot folder (cache only: raises if the model was not downloaded)."""
    from huggingface_hub import snapshot_download
    return snapshot_download(REPO, local_files_only=True,
                             allow_patterns=["run.py", "config.json", "*.safetensors", "indic_encoder/*", "LICENSE"])


class MithiTTS(TTS):
    name = "mithi"
    languages = ("hi", "bn", "kn", "en")
    license = "Apache-2.0"
    demo_only = False

    def load(self) -> None:
        d = model_dir()
        spec = importlib.util.spec_from_file_location("mithi_run", os.path.join(d, "run.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["mithi_run"] = mod
        spec.loader.exec_module(mod)
        self._mithi = mod.Mithi(device=self.options.get("device", "cpu"))
        self._lock = threading.Lock()
        self.warmed: set[str] = set()

    def synthesize(self, text: str, voice: Voice) -> Synthesis:
        self.ensure_loaded()
        lang = voice.params.get("lang", voice.language)
        with self._lock:
            audio = np.asarray(self._mithi.synthesize(text, lang=lang, voice=voice.params.get("voice", "ahana")),
                               dtype=np.float32).reshape(-1)
            self.warmed.add(lang)
        peak = float(np.abs(audio).max()) if audio.size else 0.0
        if peak > 1e-4:
            audio = audio * (PEAK / peak)
        return Synthesis(audio, SR, {"engine": "mithi"})
