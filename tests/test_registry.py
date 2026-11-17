from agent import stt, tts
from agent.llm.pricing import cost_usd


def test_registries_lazy_and_complete():
    assert set(stt.available()) == {"faster-whisper", "indicconformer", "mms"}
    assert set(tts.available()) == {"omnivoice", "indic-parler", "kokoro", "mms-tts", "mithi"}
    m = tts.create("mithi")  # lazy: no model loaded at creation
    assert m.license == "Apache-2.0" and not m.demo_only and not m._loaded
    # creating does not import heavy deps or load weights
    e = tts.create("omnivoice")
    assert e.demo_only and "CC-BY-NC" in e.license and not e._loaded


def test_cost():
    u = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert abs(cost_usd("claude-haiku-5-5", u) - 0.60) < 1e-9
