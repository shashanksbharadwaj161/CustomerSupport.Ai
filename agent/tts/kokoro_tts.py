"""Kokoro-82M (Apache-2.0). Product track candidate for en/ja.

lang_code 'a' = American English, 'j' = Japanese (needs `misaki[ja]`). English G2P needs espeak-ng.
Note: Japanese voices are graded C+ or lower in the model's own VOICES.md: listen before choosing.
"""
from __future__ import annotations

import numpy as np

from agent.tts.base import TTS, Synthesis, Voice

_LANG_CODE = {"en": "a", "ja": "j"}


class KokoroTTS(TTS):
    name = "kokoro"
    languages = ("en", "ja")
    license = "Apache-2.0"
    SAMPLE_RATE = 24000

    def load(self) -> None:
        from kokoro import KPipeline

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
