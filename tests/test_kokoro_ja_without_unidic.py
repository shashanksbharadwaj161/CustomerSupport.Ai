"""Japanese speech must work even when the 526 MB UniDic dictionary was never downloaded (Windows report)."""
import numpy as np
import pytest

kokoro = pytest.importorskip("kokoro")


def _weights():
    from agent.engines import weights_cached
    return weights_cached("hexgrad/Kokoro-82M")


@pytest.mark.skipif(not _weights(), reason="Kokoro weights not downloaded")
def test_japanese_falls_back_to_pyopenjtalk_mode(monkeypatch):
    import agent.tts.kokoro_tts as k
    from agent.voices import VoiceCatalog
    monkeypatch.setattr(k, "unidic_ready", lambda: False)
    eng = k.KokoroTTS()
    syn = eng.synthesize("お電話ありがとうございます。", VoiceCatalog().voice("kokoro_ja_alpha"))
    a = np.asarray(syn.audio)
    assert a.size > syn.sample_rate * 0.5 and float(np.abs(a).max()) > 0.05
    assert eng.ja_mode.startswith("pyopenjtalk")
