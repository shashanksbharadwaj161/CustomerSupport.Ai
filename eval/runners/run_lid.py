"""M0 language ID: accuracy over the 5 candidates (incl. mixed lines) and threshold sweep.

For each recording: Whisper LID probabilities + an auto-language transcript (for the
script check). Then, offline, every (threshold, prev_bias) pair is simulated with the
previous turn's language = same language ("stay") and = each other language ("switch").
The recommended pair maximizes the worse of stay/switch accuracy.

  python -m eval.runners.run_lid --model large-v3
"""
from __future__ import annotations

import argparse
import pathlib
import time

from agent.audio import load_audio
from agent.lang import LANGS
from agent.lang.routing import decide_language, restrict_probs
from agent.stt.faster_whisper_stt import FasterWhisperSTT
from eval.common import AUDIO, audio_for, load_lines, percentile, save

THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
BIASES = [0.0, 0.05, 0.1, 0.2, 0.3]


def simulate(records: list[dict], threshold: float, bias: float, use_script: bool = True) -> dict:
    stay_ok = stay_n = sw_ok = sw_n = 0
    for r in records:
        for prev in LANGS:
            d = decide_language(r["probs"], r["auto_text"] if use_script else None, prev,
                                threshold=threshold, prev_bias=bias)
            ok = d.language in r["accept"]
            if prev in r["accept"]:
                stay_n += 1
                stay_ok += ok
            else:
                sw_n += 1
                sw_ok += ok
    return {"threshold": threshold, "prev_bias": bias, "script_check": use_script,
            "stay_acc": round(stay_ok / stay_n, 3) if stay_n else None,
            "switch_acc": round(sw_ok / sw_n, 3) if sw_n else None}


def sweep(records: list[dict]) -> tuple[list[dict], dict | None]:
    grid = [simulate(records, t, b, s) for s in (True, False) for t in THRESHOLDS for b in BIASES]
    scored = [g for g in grid if g["stay_acc"] is not None and g["switch_acc"] is not None]
    best = max(scored, key=lambda g: (min(g["stay_acc"], g["switch_acc"]), g["switch_acc"]),
               default=None)
    return grid, best


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--audio-dir", default=str(AUDIO))
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args(argv)

    stt = FasterWhisperSTT(model=a.model)
    stt.ensure_loaded()
    audio_dir = pathlib.Path(a.audio_dir)
    records, lat = [], []
    for line in load_lines():
        path = audio_for(line["id"], audio_dir)
        if not path:
            continue
        audio = load_audio(str(path))
        t = time.perf_counter()
        probs = stt.detect_language(audio)
        lat.append((time.perf_counter() - t) * 1000)
        auto = stt.transcribe(audio, None)
        rp = restrict_probs(probs)
        top = max(rp, key=rp.get)
        records.append({"id": line["id"], "lang": line["lang"], "accept": line["accept"],
                        "category": line["category"], "probs": rp, "raw_top": top,
                        "raw_conf": round(rp[top], 3), "auto_text": auto.text})
        print(f"{line['id']}: top={top} {rp[top]:.2f} | {auto.text}")
    if not records:
        print(f"No audio in {audio_dir}.")
        return 1

    def acc(rs):
        return round(sum(r["raw_top"] in r["accept"] for r in rs) / len(rs), 3) if rs else None

    grid, best = sweep(records)
    per_lang = {l: acc([r for r in records if r["lang"] == l and r["category"] == "mono"]) for l in LANGS}
    p = save(f"lid_{a.model}{'_synthetic' if a.synthetic else ''}", {
        "kind": "lid", "model": a.model, "synthetic": a.synthetic,
        "raw_top1_mono": acc([r for r in records if r["category"] == "mono"]),
        "raw_top1_mixed": acc([r for r in records if r["category"] != "mono"]),
        "raw_top1_per_lang": per_lang,
        "detect_latency_p50_ms": percentile(lat, 0.5), "recommended": best, "grid": grid,
        "records": records})
    print(f"recommended: {best}\nsaved {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
