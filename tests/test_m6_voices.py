import io
import importlib.util

import numpy as np
import pytest
import soundfile as sf

from tests.conftest import make_client

HAS_KOKORO = importlib.util.find_spec("kokoro") is not None


def test_registry_lists_status_license_and_demo_flags(data_dir):
    c, _ = make_client()
    vs = {v["id"]: v for v in c.get("/api/voices").json()}
    assert vs["parler_hi_divya"]["license"] == "Apache-2.0"
    assert vs["omni_auto_bn"]["demo_only"] is True and "CC-BY-NC" in vs["omni_auto_bn"]["license"]
    if HAS_KOKORO:
        assert vs["kokoro_en_heart"]["status"] == "ready"
    for lang in ("en", "ja", "hi", "bn", "kn"):
        assert any(v["language"] == lang for v in vs.values()), lang
    p = c.get("/api/voices/personas").json()
    assert set(p) >= {"warm_female", "calm_male", "energetic_young", "formal_senior"}
    assert all(set(m) == {"en", "ja", "hi", "bn", "kn"} for m in p.values())


@pytest.mark.skipif(not HAS_KOKORO, reason="kokoro not installed")
def test_preview_real_kokoro_wav(data_dir):
    c, _ = make_client()
    r = c.post("/api/voices/preview", json={"voice_id": "kokoro_ja_alpha"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    audio, sr = sf.read(io.BytesIO(r.content))
    assert sr == 24000 and 2.0 < len(audio) / sr < 12.0 and np.abs(audio).max() > 0.01
    assert r.headers["x-demo-only"] == "0"


def test_preview_pending_engine_is_honest(data_dir):
    c, _ = make_client()
    if importlib.util.find_spec("parler_tts") is None:
        r = c.post("/api/voices/preview", json={"voice_id": "parler_kn_anu"})
        assert r.status_code == 503 and "PENDING" in r.json()["detail"]
    assert c.post("/api/voices/preview", json={"voice_id": "nope"}).status_code == 404


def _wav(seconds=4.0):
    sr = 24000
    t = np.arange(int(sr * seconds)) / sr
    buf = io.BytesIO()
    sf.write(buf, (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr, format="WAV")
    return buf.getvalue()


def test_add_persona_clip_requires_consent_and_transcript(data_dir):
    c, _ = make_client()
    files = {"clip": ("ref.wav", _wav(), "audio/wav")}
    base = {"language": "hi", "transcript": "नमस्ते, यह एक परीक्षण वाक्य है।", "display_name": "Model clip"}
    assert c.post("/api/voices", data=base, files=files).status_code == 400  # no consent
    assert c.post("/api/voices", data={**base, "consent": "true", "transcript": ""}, files=files).status_code == 400
    assert c.post("/api/voices", data={**base, "consent": "true"}, files={"clip": ("x.wav", _wav(0.5), "audio/wav")}).status_code == 400
    r = c.post("/api/voices", data={**base, "consent": "true", "source": "model_generated"}, files=files)
    assert r.status_code == 200 and r.json()["demo_only"] is True
    vid = r.json()["id"]
    v = next(v for v in c.get("/api/voices").json() if v["id"] == vid)
    assert v["engine"] == "omnivoice" and v["demo_only"] and v["user_added"]
    assert c.delete(f"/api/voices/{vid}").json()["ok"]


def test_live_voice_switch_applies_to_next_sentence():
    from agent.brain import CallContext
    from agent.engines import EngineManager
    from agent.pipeline.session import CallSession, Hooks
    from agent.presets import preset
    from agent.voices import VoiceCatalog
    s = CallSession(ctx=CallContext("t", preset("bank_support")), engines=EngineManager(), voices=VoiceCatalog(), hooks=Hooks(provider=lambda: None))
    assert s.voice_for("en").id == "kokoro_en_heart"
    s.ctx.voice_by_lang["en"] = "kokoro_en_michael"  # what the 'set_voice' client message does
    assert s.voice_for("en").id == "kokoro_en_michael"
    assert s.fallback_voice("hi").id == "kokoro_hi_alpha"
