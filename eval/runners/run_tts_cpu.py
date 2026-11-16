"""CPU speaking engines for hi / bn / kn (demo mode): speed + round-trip intelligibility PROXY.

  python -m eval.runners.run_tts_cpu
Voices: Kokoro Hindi (Apache-2.0, unrated) and facebook/mms-tts-{hin,ben,kan} (CC-BY-NC, DEMO ONLY, robotic
pipeline-testing voices). First audio = full sentence generation time (no engine streams). RTF = generation / audio seconds.
Round trip: synthesize each reply line, transcribe it back with the best measured STT for that language (from
fleurs_stt_*.json, oracle language), report CER vs the input. This is an intelligibility PROXY, NOT naturalness.
Audio is written to ~/.cache/shaon-eval/tts_cpu (outside the repo) for listening.
"""
from __future__ import annotations

import json
import time

import numpy as np

from agent import stt as stt_registry
from agent import tts as tts_registry
from agent.audio import load_audio, write_wav
from agent.voices import VoiceCatalog
from eval.common import EVAL, OUT, load, percentile, save
from eval.fleurs import CACHE
from eval.wer import aggregate, cer

VOICES = ["kokoro_hi_alpha", "mms_hi", "mms_bn", "mms_kn"]
WAV_DIR = CACHE.parent / "tts_cpu"


def best_stt(lang: str) -> tuple[str, dict, float | None]:
    best = None
    for f in OUT.glob("fleurs_stt_*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        v = (d.get("per_lang") or {}).get(lang)
        if d.get("status") == "measured" and v and v.get("wer") is not None and (best is None or v["wer"] < best[2]):
            name = d["engine"]
            best = ("faster-whisper", {"model": name.split("-", 1)[1], "device": "cpu", "compute_type": "int8"}, v["wer"]) \
                if name.startswith("whisper-") else (name, {}, v["wer"])
    return best or ("faster-whisper", {"model": "small", "device": "cpu", "compute_type": "int8"}, None)


def main():
    lines = json.loads((EVAL / "fixtures" / "reply_lines.json").read_text(encoding="utf-8"))
    cat = VoiceCatalog()
    WAV_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for vid in VOICES:
        v = cat.voice(vid)
        eng = tts_registry.create(v.engine)
        t0 = time.perf_counter()
        eng.ensure_loaded()
        eng.synthesize(lines[v.language][0], v)  # warm-up (+ first model load for MMS), excluded
        load_s = time.perf_counter() - t0
        rows = []
        for i, text in enumerate(lines[v.language]):
            t = time.perf_counter()
            s = eng.synthesize(text, v)
            gen = time.perf_counter() - t
            dur = len(s.audio) / s.sample_rate
            path = WAV_DIR / f"{vid}_{i}.wav"
            write_wav(str(path), s.audio, s.sample_rate)
            rows.append({"i": i, "text": text, "gen_ms": round(gen * 1000), "audio_s": round(dur, 2), "rtf": round(gen / max(dur, 0.01), 3),
                         "wav": str(path), "peak": round(float(np.abs(s.audio).max()), 3)})
        results[vid] = {"lang": v.language, "engine": v.engine, "license": v.license, "demo_only": v.demo_only,
                        "load_and_warmup_s": round(load_s, 1), "first_audio_median_ms": percentile([r["gen_ms"] for r in rows], 0.5),
                        "first_audio_p90_ms": percentile([r["gen_ms"] for r in rows], 0.9),
                        "rtf_median": round(float(np.median([r["rtf"] for r in rows])), 3), "rows": rows}
        print(vid, "first audio median", results[vid]["first_audio_median_ms"], "ms, RTF", results[vid]["rtf_median"])
        del eng
    stt_cache = {}
    for vid, res in results.items():
        name, opts, wer = best_stt(res["lang"])
        key = name + json.dumps(opts, sort_keys=True)
        if key not in stt_cache:
            stt_cache[key] = stt_registry.create(name, **opts)
        stt = stt_cache[key]
        scores = []
        for r in res["rows"]:
            hyp = stt.transcribe(load_audio(r["wav"]), res["lang"]).text
            e, n = cer(r["text"], hyp)
            r["roundtrip_hyp"], r["roundtrip_cer"] = hyp, round(e / max(n, 1), 3)
            scores.append({"cer_err": e, "cer_n": n})
        res["roundtrip_cer"] = aggregate(scores).get("cer")
        res["roundtrip_stt"] = f"{name} {opts.get('model', '')}".strip() + (f" (FLEURS WER {wer})" if wer is not None else "")
        print(vid, "round-trip CER", res["roundtrip_cer"], "via", res["roundtrip_stt"])
    save("tts_cpu", {"kind": "tts_cpu", "note": "Round-trip CER is an intelligibility PROXY, not naturalness. MMS voices are robotic pipeline-testing voices (CC-BY-NC, demo only). Reply lines are machine-written (native review pending).",
                     "voices": results})


if __name__ == "__main__":
    main()
