"""Regression: "RouterTTS ... TTS context ... completed with no audio" (Windows live call: very slow or no agent voice).

Root cause: pipecat's TTSService ends an audio context when no audio arrives for `stop_frame_timeout_s` (default 3 s).
RouterTTS synthesises a whole sentence in a worker thread, so any sentence that takes longer than 3 s (cold Kokoro, a
slower CPU, MMS, Mithi...) closed its context as SILENT, an error was pushed, and after 3 in a row the service was marked
permanently unusable: no agent audio for the rest of the call. These tests run the REAL RouterTTS inside a real pipecat
pipeline with a deliberately slow fake engine.
"""
import asyncio
import time

import numpy as np
import pytest

pytest.importorskip("pipecat")

from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame, TTSSpeakFrame  # noqa: E402
from pipecat.tests.utils import run_test  # noqa: E402

from agent.brain import CallContext  # noqa: E402
from agent.presets import preset  # noqa: E402
from agent.tts.base import Synthesis  # noqa: E402


class SlowEngine:
    _loaded = True

    def __init__(self, delay):
        self.delay = delay

    def ensure_loaded(self):
        pass

    def synthesize(self, text, voice):
        time.sleep(self.delay)  # slower than pipecat's 3 s audio-context timeout
        t = np.linspace(0, 1.2, int(24000 * 1.2), endpoint=False)
        return Synthesis((0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), 24000)


class FakeEngines:
    cfg = {"default_voices": {"en": "kokoro_en_heart"}, "cpu_fallback_voices": {}, "lid": {}}
    cuda = False

    def __init__(self, delay):
        self.eng = SlowEngine(delay)

    def get_tts(self, name):
        return self.eng


def make_session(delay):
    from agent.pipeline.session import CallSession, Hooks
    from agent.voices import VoiceCatalog
    prof = preset("bank_support")
    ctx = CallContext(call_id="call_test", profile=prof)
    ctx.voice_by_lang["en"] = "kokoro_en_heart"
    return CallSession(ctx=ctx, engines=FakeEngines(delay), voices=VoiceCatalog(), hooks=Hooks(provider=lambda: None))


@pytest.mark.parametrize("delay", [0.2, 4.5])
def test_slow_synthesis_still_reaches_the_transport(delay):
    from agent.pipeline.services import RouterTTS
    tts = RouterTTS(make_session(delay))
    down, up = asyncio.run(run_test(tts, frames_to_send=[TTSSpeakFrame("Hello, thank you for calling.")]))
    audio = [f for f in down if isinstance(f, TTSAudioRawFrame)]
    errors = [f for f in list(down) + list(up) if isinstance(f, ErrorFrame)]
    assert sum(len(f.audio) for f in audio) >= 24000 * 2 * 1.0, f"no/short audio after {delay}s synthesis"
    assert not [e for e in errors if "no audio" in str(getattr(e, "error", e))], errors


def test_silent_language_does_not_mute_the_service():
    """A sentence with no available voice must not make the TTS service unusable for later sentences."""
    from agent.pipeline.services import RouterTTS
    session = make_session(0.1)
    tts = RouterTTS(session)
    real = session.voice_for

    def voice_for(lang, _real=real):
        return None if lang == "kn" else _real(lang)
    session.voice_for = voice_for
    session.fallback_voices = lambda lang: []
    frames = [TTSSpeakFrame(t) for t in ("ನಮಸ್ಕಾರ.", "ನಮಸ್ಕಾರ.", "ನಮಸ್ಕಾರ.", "ನಮಸ್ಕಾರ.", "Hello again, how can I help?")]
    down, _ = asyncio.run(run_test(tts, frames_to_send=frames))
    assert any(isinstance(f, TTSAudioRawFrame) for f in down), "English after 4 silent Kannada sentences produced no audio"
