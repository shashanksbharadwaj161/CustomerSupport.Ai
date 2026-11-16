"""Language routing through CallSession.transcribe_turn with stub engines (no models)."""
import numpy as np
import pytest

from agent.brain import CallContext
from agent.pipeline.session import CallSession, Hooks
from agent.presets import preset
from agent.stt.base import Transcript
from agent.voices import VoiceCatalog


class StubSTT:
    def __init__(self, name, model, script):
        self.name, self.options, self.script = name, {"model": model}, script
        self.calls = []

    def transcribe(self, audio, language):
        self.calls.append(language)
        text, detected, probs = self.script(language)
        return Transcript(text=text, language=detected, lid_probs=probs if language is None else {})


class StubEngines:
    def __init__(self, script, indic=False):
        self.cfg = {"lid": {"threshold": 0.5, "prev_bias": 0.1}, "default_voices": {}}
        self.whisper = StubSTT("faster-whisper", "small", script)
        self.indic = StubSTT("indicconformer", None, script)
        self.use_indic = indic

    def stt_choice(self, lang):
        if self.use_indic and lang in ("hi", "bn", "kn"):
            return "indicconformer", {"decoding": "rnnt"}
        return "faster-whisper", {"model": "small"}

    def stt_route(self, lang):
        name, opts = self.stt_choice(lang)
        return name, opts, []

    load_errors: dict = {}

    def get_stt(self, name, opts):
        return self.indic if name == "indicconformer" else self.whisper

    def lid_engine(self):
        return self.whisper


TEXT = {"en": "what time do you open", "ja": "何時に開きますか", "hi": "आप कब खुलते हैं", "bn": "আপনারা কখন খোলেন", "kn": "ನೀವು ಯಾವಾಗ ತೆರೆಯುತ್ತೀರಿ"}


def session(script, langs=("en", "ja", "hi", "bn", "kn"), indic=False, prev="en"):
    p = preset("bank_support")
    p["languages"]["enabled"] = list(langs)
    p["languages"]["default"] = prev
    s = CallSession(ctx=CallContext(call_id="t", profile=p), engines=StubEngines(script, indic), voices=VoiceCatalog(),
                    hooks=Hooks(provider=lambda: None))
    return s


AUDIO = np.zeros(16000, dtype=np.float32)


def test_confident_lid_switches_language_single_pass():
    def script(lang):
        return (TEXT[lang or "ja"], "ja", {"ja": 0.92, "en": 0.05, "hi": 0.03})
    s = session(script)
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] == "ja" and info["reason"] == "lid" and info["text"] == TEXT["ja"]
    assert s.engines.whisper.calls == [None]  # one pass gave probabilities + text
    assert s.ctx.current_lang == "ja"


def test_low_confidence_keeps_previous_language_or_uses_dual_recognition():
    # top = bn but weak; previous = hi. Dual recognition: keep the transcript whose script matches.
    def script(lang):
        if lang is None:
            return (TEXT["bn"], "bn", {"bn": 0.40, "hi": 0.35, "en": 0.25})
        return (TEXT[lang], lang, {})
    s = session(script, prev="hi")
    info = s.transcribe_turn(AUDIO)
    assert info["reason"] == "dual_recognition" and info["lang"] == "bn" and info["text"] == TEXT["bn"]

    # same weak LID but the candidate transcript is not in Bengali script -> keep the previous language
    def script2(lang):
        if lang is None:
            return ("amar card", "bn", {"bn": 0.40, "hi": 0.35, "en": 0.25})
        return (TEXT[lang], lang, {})
    s = session(script2, prev="hi")
    info = s.transcribe_turn(AUDIO)
    assert info["reason"] == "dual_recognition" and info["lang"] == "hi" and info["text"] == TEXT["hi"]


def test_low_confidence_same_top_as_previous_keeps_it():
    def script(lang):
        return (TEXT[lang or "hi"], "hi", {"hi": 0.40, "bn": 0.35, "en": 0.25})
    s = session(script, prev="hi")
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] == "hi"


def test_script_flip_only_when_lid_is_unsure():
    # LID unsure between hi and bn; the transcript is clearly Bengali script -> flip to bn and re-run bn STT
    def script(lang):
        if lang is None:
            return (TEXT["bn"], "hi", {"hi": 0.55, "bn": 0.45})
        return (TEXT[lang], lang, {})
    s = session(script, prev="hi")
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] == "bn" and info["reason"] == "script_flip"


def test_confident_lid_is_not_overridden_by_a_hallucinated_script():
    # measured on FLEURS: Whisper small sometimes hallucinates in another script while LID was confidently right
    def script(lang):
        if lang is None:
            return (TEXT["kn"], "bn", {"bn": 0.9, "kn": 0.1})
        return (TEXT[lang], lang, {})
    s = session(script, prev="en")
    assert s.transcribe_turn(AUDIO)["lang"] == "bn"


def test_manual_override_wins_and_disabled_languages_ignored():
    def script(lang):
        return (TEXT[lang or "ja"], "ja", {"ja": 0.99, "en": 0.01})
    s = session(script, langs=("en", "hi"))
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] in ("en", "hi")  # ja is not enabled for this agent
    s.ctx.override_lang = "hi"
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] == "hi" and info["reason"] == "override"


def test_single_language_agent_skips_lid():
    def script(lang):
        assert lang == "en", "single-language agent must not run language ID"
        return (TEXT["en"], "en", {})
    s = session(script, langs=("en",))
    assert s.transcribe_turn(AUDIO)["reason"] == "single_language"


def test_indic_languages_route_to_indicconformer_when_configured():
    def script(lang):
        if lang is None:
            return ("x", "kn", {"kn": 0.9, "en": 0.1})
        return (TEXT[lang], lang, {})
    s = session(script, indic=True)
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] == "kn" and s.engines.indic.calls == ["kn"]
    assert any(e.startswith("faster-whisper") or e.startswith("indicconformer") for e in info["engines"])


@pytest.mark.parametrize("pair", [("en", "ja"), ("ja", "hi"), ("hi", "bn"), ("bn", "kn"), ("kn", "en")])
def test_three_consecutive_switch_directions(pair):
    """PLAN M3 pass rule, simulated: A->B, B->A, A->B with confident LID each turn."""
    a, b = pair
    seq = [b, a, b]
    state = {"i": 0}

    def script(lang):
        target = seq[state["i"]]
        return (TEXT[lang or target], target, {target: 0.9, "en" if target != "en" else "ja": 0.1})
    s = session(script, prev=a)
    for want in seq:
        info = s.transcribe_turn(AUDIO)
        assert info["lang"] == want
        state["i"] += 1


def test_reply_language_from_script_not_model_claim():
    import asyncio
    from agent.brain import TurnEngine
    from agent.llm.provider import FakeProvider
    # model is asked in Kannada but answers in English: the TTS language must follow the SCRIPT (en)
    prov = FakeProvider(script=lambda m, s: "Sure, we open at nine.")
    ctx = CallContext(call_id="t", profile=preset("bank_support"))
    out = []

    async def emit(k, d):
        out.append(d)
    asyncio.run(TurnEngine(ctx, prov, "m").respond(TEXT["kn"], "kn", emit))
    assert out[0]["lang"] == "en"


def test_indic_engine_failure_falls_back_to_whisper_in_same_turn():
    def script(lang):
        if lang is None:
            return ("x", "hi", {"hi": 0.9, "en": 0.1})
        return (TEXT[lang], lang, {})
    s = session(script, indic=True)

    class Boom:
        options = {}

        def transcribe(self, a, l):
            raise OSError("gated repo: accept terms + HF_TOKEN")
    s.engines.indic = Boom()
    s.engines.load_errors = {}
    orig = s.engines.stt_choice
    s.engines.stt_choice = lambda lang: ("faster-whisper", {"model": "small"}) if "indicconformer" in s.engines.load_errors else orig(lang)
    s.engines.stt_route = lambda lang: (*s.engines.stt_choice(lang), [])
    info = s.transcribe_turn(AUDIO)
    assert info["lang"] == "hi" and info["text"] == TEXT["hi"] and "next in order" in info["fallbacks"][0]


def test_engine_manager_routing_order_and_skip_reasons(monkeypatch):
    from agent import engines as E
    em = E.EngineManager()
    em.cuda = False
    em.cfg["stt_cpu"]["kn"] = {"order": [{"engine": "indicconformer", "options": {}}, {"engine": "mms", "options": {}},
                                        {"engine": "faster-whisper", "options": {"model": "small"}}]}
    monkeypatch.setattr(E, "installed", lambda n: True)
    monkeypatch.setattr(E, "weights_cached", lambda repo: False)
    monkeypatch.setattr(E, "_hf_token", lambda: False)
    name, opts, skipped = em.stt_route("kn")
    assert name == "mms" and skipped == ["indicconformer: gated weights not downloaded and no HF token"]
    em.load_errors["mms"] = "OSError: out of memory"
    name, opts, skipped = em.stt_route("kn")
    assert name == "faster-whisper" and opts["model"] == "small" and len(skipped) == 2
    monkeypatch.setattr(E, "_hf_token", lambda: True)
    em.load_errors.clear()
    assert em.stt_route("kn")[0] == "indicconformer"
    # old single-engine entries still work, whisper is always appended as the last resort
    em.cfg["stt_cpu"]["en"] = {"engine": "faster-whisper", "options": {"model": "small"}}
    assert [n for n, _ in em.stt_candidates("en")] == ["faster-whisper"]
