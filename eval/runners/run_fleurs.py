"""Real-audio STT + language-ID evaluation on google/fleurs (CC-BY-4.0) test clips, on THIS machine's CPU.

  python -m eval.runners.run_fleurs --stt whisper-small whisper-base mms indicconformer --lid
STT is scored with the true language given (oracle) to separate recognition from language ID.
Language ID runs the APP's real path (CallSession.transcribe_turn, all five languages enabled, call starting in English).
Caveat written into every output: FLEURS = clean read Wikipedia-style speech, not phone calls (optimistic);
Whisper small/base are CPU stand-ins for the GPU engines.
"""
from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np

from agent.audio import load_audio
from eval.common import percentile, save
from eval.fleurs import fetch
from eval.wer import aggregate, has_digits, score

LANGS = ["en", "ja", "hi", "bn", "kn"]
CAVEAT = ("FLEURS is clean read Wikipedia-style speech, not phone calls: numbers are optimistic for live calls. "
          "Whisper small/base on CPU are stand-ins for the GPU engines (large-v3, IndicConformer). Measured on this machine's CPU.")


def hf_bytes(repo: str) -> int | None:
    try:
        from huggingface_hub import scan_cache_dir
        for r in scan_cache_dir().repos:
            if r.repo_id == repo:
                return r.size_on_disk
    except Exception:
        pass
    return None


def make_engine(name: str):
    if name.startswith("whisper-"):
        from agent.stt.faster_whisper_stt import FasterWhisperSTT
        size = name.split("-", 1)[1]
        # exactly the app's CPU decoding (agent/engines.json stt_cpu): greedy, no temperature-fallback retries
        return (FasterWhisperSTT(model=size, device="cpu", compute_type="int8", beam_size=1, temperature=0.0),
                f"Systran/faster-whisper-{size}", "int8 CTranslate2, greedy beam 1, temperature 0", ("en", "ja", "hi", "bn", "kn"))
    if name == "mms":
        from agent.stt.mms_stt import MMSSTT
        return MMSSTT(), "facebook/mms-1b-all", "fp32 PyTorch, CC-BY-NC (eval only)", ("hi", "bn", "kn")
    if name == "indicconformer":
        from agent.stt.indicconformer_stt import IndicConformerSTT
        return IndicConformerSTT(), "ai4bharat/indic-conformer-600m-multilingual", "transformers remote code", ("hi", "bn", "kn")
    raise SystemExit(f"unknown engine {name}")


def run_stt(name: str, n: int, mms_n: int) -> None:
    eng, repo, fmt, langs = make_engine(name)
    t0 = time.perf_counter()
    try:
        eng.ensure_loaded()
    except Exception as e:
        reason = f"{type(e).__name__}: {str(e)[:200]}"
        print(f"{name}: PENDING ({reason})")
        save(f"fleurs_stt_{name}", {"kind": "fleurs_stt", "engine": name, "repo": repo, "status": "PENDING", "reason": reason, "caveat": CAVEAT})
        return
    load_s = time.perf_counter() - t0
    rows = []
    for lang in langs:
        clips = fetch(lang, mms_n if name == "mms" else n)
        for c in clips:
            audio = load_audio(c["wav"])
            t = time.perf_counter()
            hyp = eng.transcribe(audio, lang).text
            ms = (time.perf_counter() - t) * 1000
            r = {"id": c["id"], "lang": lang, "ref": c["text"], "hyp": hyp, "ms": round(ms), "audio_s": c["seconds"],
                 "ref_has_digits": has_digits(c["text"]), **score(lang, c["text"], hyp)}
            rows.append(r)
        print(f"{name} {lang}: done {len(clips)}", flush=True)
        _save_stt(name, repo, fmt, load_s, langs, rows, partial=lang != langs[-1])


def _save_stt(name, repo, fmt, load_s, langs, rows, partial=False) -> None:
    per = {}
    for lang in sorted({r["lang"] for r in rows}, key=langs.index):
        rs = [r for r in rows if r["lang"] == lang]
        lat = [r["ms"] for r in rs]
        per[lang] = {"n": len(rs), **aggregate(rs), "no_digit_refs": {"n": sum(not r["ref_has_digits"] for r in rs), **aggregate([r for r in rs if not r["ref_has_digits"]])},
                     "latency_median_ms": percentile(lat, 0.5), "latency_p90_ms": percentile(lat, 0.9),
                     "rtf_median": round(float(np.median([r["ms"] / 1000 / r["audio_s"] for r in rs])), 3),
                     "audio_minutes": round(sum(r["audio_s"] for r in rs) / 60, 1)}
        m = "cer" if lang == "ja" else "wer"
        print(f"  {lang}: n={per[lang]['n']} {m}={per[lang].get(m)} cer={per[lang].get('cer')} median={per[lang]['latency_median_ms']} ms", flush=True)
    save(f"fleurs_stt_{name}", {"kind": "fleurs_stt", "engine": name, "repo": repo, "format": fmt, "weights_bytes": hf_bytes(repo),
                                "load_s": round(load_s, 1), "status": "partial" if partial else "measured", "caveat": CAVEAT, "per_lang": per, "rows": rows})


def run_lid(n: int) -> None:
    from agent.brain import CallContext
    from agent.engines import EngineManager
    from agent.pipeline.session import CallSession, Hooks
    from agent.presets import preset
    from agent.voices import VoiceCatalog
    from eval.runners.run_lid import sweep

    em = EngineManager()
    em.cfg["stt_cpu"] = {l: {"engine": "faster-whisper", "options": {"model": "small", "beam_size": 1, "temperature": 0.0}} for l in LANGS}
    em.cuda = False
    rows = []
    for lang in LANGS:
        for c in fetch(lang, n):
            prof = preset("bank_support")  # all five languages enabled, call starts in English
            s = CallSession(ctx=CallContext("lid-eval", prof), engines=em, voices=VoiceCatalog(), hooks=Hooks(provider=lambda: None))
            audio = load_audio(c["wav"])
            t = time.perf_counter()
            info = s.transcribe_turn(audio)
            ms = (time.perf_counter() - t) * 1000
            probs = info.get("lid_probs") or {}
            top = max(probs, key=probs.get) if probs else None
            rows.append({"id": c["id"], "lang": lang, "accept": [lang], "probs": probs, "auto_text": info.get("lid_text") or "",
                         "raw_top": top, "raw_conf": probs.get(top) if top else None, "app_lang": info["lang"],
                         "app_reason": info["reason"], "lid_ms": info.get("lid_ms"), "turn_ms": round(ms)})
        print(f"lid {lang}: done", flush=True)
    conf = {t: {p: 0 for p in LANGS} for t in LANGS}
    conf_app = {t: {p: 0 for p in LANGS} for t in LANGS}
    for r in rows:
        if r["raw_top"]:
            conf[r["lang"]][r["raw_top"]] += 1
        conf_app[r["lang"]][r["app_lang"]] += 1
    acc = lambda rs, k: round(sum(r[k] == r["lang"] for r in rs) / len(rs), 3) if rs else None
    grid, best = sweep(rows)
    per = {l: {"n": sum(r["lang"] == l for r in rows), "raw_top1": acc([r for r in rows if r["lang"] == l], "raw_top"),
               "app_from_en": acc([r for r in rows if r["lang"] == l], "app_lang"),
               "median_conf": percentile([r["raw_conf"] for r in rows if r["lang"] == l and r["raw_conf"] is not None], 0.5)} for l in LANGS}
    print("raw top-1:", {l: per[l]["raw_top1"] for l in LANGS}, "\napp (call starts in English):", {l: per[l]["app_from_en"] for l in LANGS})
    print("recommended:", best)
    save("fleurs_lid", {"kind": "fleurs_lid", "engine": "faster-whisper small int8 (app LID path)", "caveat": CAVEAT,
                        "note": "Proposed thresholds are CPU / read-speech estimates: re-measure on the demo PC with real call audio.",
                        "per_lang": per, "overall_raw_top1": acc(rows, "raw_top"), "overall_app": acc(rows, "app_lang"),
                        "confusion_raw": conf, "confusion_app_from_en": conf_app, "recommended": best, "grid": grid,
                        "lid_ms_median": percentile([r["lid_ms"] for r in rows if r["lid_ms"]], 0.5), "rows": rows})


def rescore() -> None:
    """Add the labelled Indic-folded metric to saved results (offline; no audio needed)."""
    import json
    from eval.common import OUT
    from eval.wer import score_folded
    for f in OUT.glob("fleurs_stt_*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("status") != "measured":
            continue
        for lang, v in d["per_lang"].items():
            rs = [r for r in d["rows"] if r["lang"] == lang]
            v["indic_folded"] = aggregate([score_folded(lang, r["ref"], r["hyp"]) for r in rs])
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f.name, {l: v.get("indic_folded") for l, v in d["per_lang"].items() if l in ("hi", "bn", "kn")})
    lf = OUT / "fleurs_lid.json"
    if lf.exists():  # recompute the app decision with the CURRENT routing rules from the stored LID outputs (deterministic)
        from agent.engines import load_engines_config
        from agent.lang.routing import decide_language
        from eval.runners.run_lid import sweep
        d = json.loads(lf.read_text(encoding="utf-8"))
        lid = load_engines_config()["lid"]
        conf = {t: {p: 0 for p in LANGS} for t in LANGS}
        for r in d["rows"]:
            dec = decide_language(r["probs"], r["auto_text"], "en", threshold=float(lid["threshold"]), prev_bias=float(lid["prev_bias"]),
                                  script_override_max_conf=float(lid.get("script_override_max_conf", 0.6)))
            r["app_lang_current_rules"] = dec.language
            conf[r["lang"]][dec.language] += 1
        d["confusion_app_current_rules"] = conf
        for l in LANGS:
            rs = [r for r in d["rows"] if r["lang"] == l]
            d["per_lang"][l]["app_current_rules"] = round(sum(r["app_lang_current_rules"] == l for r in rs) / len(rs), 3)
        d["overall_app_current_rules"] = round(sum(r["app_lang_current_rules"] == r["lang"] for r in d["rows"]) / len(d["rows"]), 3)
        d["current_rules"] = {k: lid.get(k) for k in ("threshold", "prev_bias", "script_override_max_conf")}
        d["grid"], d["recommended"] = sweep(d["rows"])
        lf.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print("LID app decision with current rules:", {l: d["per_lang"][l]["app_current_rules"] for l in LANGS}, "recommended", d["recommended"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stt", nargs="*", default=[])
    ap.add_argument("--lid", action="store_true")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--mms-n", type=int, default=20)
    ap.add_argument("--rescore", action="store_true", help="add the Indic-folded metric to saved results")
    a = ap.parse_args()
    if a.rescore:
        rescore()
    for e in a.stt:
        run_stt(e, a.n, a.mms_n)
    if a.lid:
        run_lid(a.n)
