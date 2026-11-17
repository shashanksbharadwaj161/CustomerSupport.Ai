"""Kokoro-82M (Apache-2.0). Product track candidate for en/ja.

lang_code 'a' = American English, 'j' = Japanese (needs `misaki[ja]`). English G2P needs espeak-ng.
Note: Japanese voices are graded C+ or lower in the model's own VOICES.md: listen before choosing.
"""
from __future__ import annotations

import numpy as np

from agent.tts.base import TTS, Synthesis, Voice

_LANG_CODE = {"en": "a", "ja": "j", "hi": "h"}  # Hindi voices exist (hf_*, hm_*): CPU candidate, quality unrated


def _short_espeak_data_path() -> None:
    """espeak-ng ignores a data folder whose path is 160+ characters (230+ on Windows) and falls back to the path it was
    built with, then EXITS the process ("Error processing file .../phontab"). Measured here: a venv path of exactly 160
    characters crashed, 156 worked. Deep install folders (OneDrive, Downloads/<long zip name>) can hit this, so copy the
    21 MB data folder to a short path once and point phonemizer at it."""
    import os
    import shutil
    import tempfile
    try:
        import espeakng_loader
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
    except Exception:
        return
    src = espeakng_loader.get_data_path()
    if len(str(src)) < 150:
        return
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    dst = os.path.join(base, "shaon-espeak-ng-data")
    if not os.path.exists(os.path.join(dst, "phontab")):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    EspeakWrapper.set_data_path(dst)


class KokoroTTS(TTS):
    name = "kokoro"
    languages = ("en", "ja", "hi")
    license = "Apache-2.0"
    SAMPLE_RATE = 24000

    def load(self) -> None:
        from kokoro import KPipeline

        try:
            import misaki.espeak  # noqa: F401  (sets the long default path on import; override it after)
        except Exception:
            pass
        _short_espeak_data_path()
        self._KPipeline = KPipeline
        self.pipelines = {}

    def _pipe(self, lang: str):
        if lang not in self.pipelines:
            self.pipelines[lang] = self._KPipeline(lang_code=_LANG_CODE[lang])
        return self.pipelines[lang]

    def synthesize(self, text: str, voice: Voice) -> Synthesis:
        self.ensure_loaded()
        chunks = [np.asarray(audio, dtype=np.float32)
                  for _gs, _ps, audio in self._pipe(voice.language)(text, voice=voice.params["voice"])]
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return Synthesis(audio, self.SAMPLE_RATE)
