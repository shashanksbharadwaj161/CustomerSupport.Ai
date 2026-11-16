import json

from eval.common import load_lines
from eval.runners.run_lid import simulate, sweep
from eval.runners.run_llm import check_reply
from eval.wer import aggregate, cer, normalize, score, wer
from agent.lang.script import dominant_language, is_native_script


def test_normalize_strips_punct_and_danda():
    assert normalize("Hello, World!") == "hello world"
    assert normalize("नमस्ते। कैसे हैं?") == "नमस्ते कैसे हैं"


def test_wer_cer():
    assert wer("a b c", "a x c") == (1, 3)
    assert cer("abc", "abd") == (1, 3)
    assert "wer_err" not in score("ja", "こんにちは", "こんにちは")
    assert aggregate([score("en", "a b", "a b"), score("en", "a b", "a c")])["wer"] == 0.25


def test_lines_file_matches_spec():
    lines = load_lines()
    assert len(lines) == 60
    assert len({l["id"] for l in lines}) == 60
    for lang in ("en", "ja", "hi", "bn", "kn"):
        mono = [l for l in lines if l["lang"] == lang and l["category"] == "mono"]
        assert len(mono) == 10
        for l in mono:
            assert dominant_language(l["text"])[0] == lang, l["id"]
            assert is_native_script(l["text"], lang), l["id"]
    assert sum(l["category"] != "mono" for l in lines) == 10


def test_check_reply():
    ok = check_reply("नमस्ते, शाखा शनिवार को दस बजे खुलती है।", ["hi"])
    assert ok["lang_ok"] and ok["native_ok"] and ok["no_digits"] and ok["short_ok"] and ok["format_ok"]
    bad = check_reply("Namaste, branch 10 baje khulti hai. **Thanks**! Visit https://x.y. Bye.", ["hi"])
    assert not bad["lang_ok"] and not bad["no_digits"] and not bad["format_ok"] and not bad["short_ok"]


def test_lid_sweep_on_synthetic_records():
    recs = [
        {"probs": {"en": 0.9, "ja": 0.025, "hi": 0.025, "bn": 0.025, "kn": 0.025}, "auto_text": "hello", "accept": ["en"]},
        {"probs": {"en": 0.1, "ja": 0.05, "hi": 0.45, "bn": 0.35, "kn": 0.05}, "auto_text": "আমার কার্ড", "accept": ["bn"]},
    ]
    r = simulate(recs, 0.5, 0.0)
    assert r["switch_acc"] == 1.0  # bn caught by script flip, en by LID
    grid, best = sweep(recs)
    assert best is not None and len(grid) > 10


def test_configs_parse():
    from eval.common import ROOT
    json.loads((ROOT / "agent" / "engines.json").read_text())
    v = json.loads((ROOT / "voices" / "bakeoff_voices.json").read_text())
    ids = {x["id"] for x in v["voices"]}
    for x in v["voices"]:
        if x["engine"] == "omnivoice":
            assert x["demo_only"] is True
        ref = x["params"].get("ref_from")
        assert ref is None or (ref in ids and not ref.startswith("omni"))
