from agent.lang.routing import bias_previous, decide_language, restrict_probs


def test_override_wins():
    d = decide_language({"en": 0.99}, "hello", "en", override="kn")
    assert (d.language, d.reason) == ("kn", "override")


def test_script_flip_beats_unsure_lid_only():
    d = decide_language({"hi": 0.55, "bn": 0.45}, "আমার কার্ড ব্লক করে দিন", "hi")
    assert (d.language, d.reason) == ("bn", "script_flip")
    d = decide_language({"hi": 0.9, "bn": 0.1}, "আমার কার্ড ব্লক করে দিন", "hi")
    assert d.language == "hi"


def test_latin_transcript_never_flips():
    # romanized Hindi looks Latin; LID decides
    d = decide_language({"hi": 0.8, "en": 0.2}, "mera balance kitna hai", "en", threshold=0.5)
    assert d.language == "hi"


def test_low_confidence_keeps_previous():
    d = decide_language({"hi": 0.4, "bn": 0.35, "en": 0.25}, None, "kn", threshold=0.6, prev_bias=0.0)
    assert (d.language, d.reason) == ("kn", "low_conf_keep_prev")


def test_restrict_and_bias():
    p = restrict_probs({"en": 0.5, "fr": 0.4, "hi": 0.1})
    assert set(p) == {"en", "ja", "hi", "bn", "kn"} and abs(sum(p.values()) - 1) < 1e-9
    b = bias_previous(p, "hi", 0.5)
    assert b["hi"] > p["hi"] and abs(sum(b.values()) - 1) < 1e-9


def test_default_without_anything():
    assert decide_language(None, None, None).language == "en"
