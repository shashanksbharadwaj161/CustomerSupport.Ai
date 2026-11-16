"""M0 STT bake-off: WER/CER and latency per language for one engine config.

Language is given to the recognizer (oracle), so this measures recognition only;
language ID is measured separately in run_lid.py.

  python -m eval.runners.run_stt --engine faster-whisper --model large-v3
  python -m eval.runners.run_stt --engine faster-whisper --model turbo
  python -m eval.runners.run_stt --engine indicconformer --decoding rnnt
  python -m eval.runners.run_stt --engine indicconformer --decoding ctc

Audio: eval/audio/<line_id>.wav from native speakers. --audio-dir can point at TTS output
for a PIPELINE CHECK ONLY (marked synthetic; never reported as WER).
"""
from __future__ import annotations

import argparse
import pathlib
import time

from agent import stt as stt_registry
from agent.audio import load_audio
from eval.common import AUDIO, GpuMem, audio_for, load_lines, percentile, save
from eval.wer import aggregate, score


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=stt_registry.available())
    ap.add_argument("--model", help="faster-whisper model name (large-v3, turbo, tiny...)")
    ap.add_argument("--decoding", help="indicconformer: ctc | rnnt")
    ap.add_argument("--device")
    ap.add_argument("--langs", nargs="*")
    ap.add_argument("--audio-dir", default=str(AUDIO))
    ap.add_argument("--synthetic", action="store_true", help="audio is TTS output: pipeline check only")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)

    opts = {k: v for k, v in {"model": a.model, "decoding": a.decoding, "device": a.device}.items() if v}
    engine = stt_registry.create(a.engine, **opts)
    audio_dir = pathlib.Path(a.audio_dir)
    lines = [l for l in load_lines(a.langs) if l["lang"] in engine.languages]
    todo = [(l, audio_for(l["id"], audio_dir)) for l in lines]
    missing = [l["id"] for l, p in todo if p is None]
    todo = [(l, p) for l, p in todo if p is not None]
    if not todo:
        print(f"No audio found in {audio_dir}. Record lines with eval/tools/recorder.html first.")
        return 1

    with GpuMem() as mem:
        t0 = time.perf_counter()
        engine.ensure_loaded()
        load_s = time.perf_counter() - t0
        warm = load_audio(str(todo[0][1]))
        engine.transcribe(warm, todo[0][0]["lang"])  # warm-up, excluded from timings

        rows = []
        for line, path in todo:
            audio = load_audio(str(path))
            t = time.perf_counter()
            tr = engine.transcribe(audio, line["lang"])
            ms = (time.perf_counter() - t) * 1000
            row = {"id": line["id"], "lang": line["lang"], "category": line["category"],
                   "numbers": line["numbers"],
                   "ref": line["text"], "hyp": tr.text, "latency_ms": round(ms),
                   "audio_s": round(len(audio) / 16000, 2)}
            if not line["romanized"]:  # romanized refs cannot be compared to native-script output
                row.update(score(line["lang"], line["text"], tr.text))
            rows.append(row)
            print(f"{line['id']}: {ms:6.0f} ms | {tr.text}")

    per_lang = {}
    for lang in sorted({r["lang"] for r in rows}):
        rs = [r for r in rows if r["lang"] == lang]
        mono = [r for r in rs if r["category"] == "mono"]
        lat = [r["latency_ms"] for r in rs]
        per_lang[lang] = {
            "n": len(rs), **aggregate(mono),
            # recognizers often write numbers as digits while references spell them out:
            # this excludes the two number lines so formatting does not mask recognition
            "no_numbers": aggregate([r for r in mono if not r["numbers"]]),
            "mixed": aggregate([r for r in rs if r["category"] != "mono"]),
            "latency_p50_ms": percentile(lat, 0.5), "latency_p90_ms": percentile(lat, 0.9),
            "rtf_mean": round(sum(r["latency_ms"] / 1000 / max(r["audio_s"], 0.01) for r in rs) / len(rs), 3),
        }
    name = f"stt_{a.engine}_{a.model or a.decoding or 'default'}{'_' + a.tag if a.tag else ''}"
    name += "_synthetic" if a.synthetic else ""
    p = save(name, {"kind": "stt", "engine": a.engine, "options": opts, "synthetic": a.synthetic,
                    "load_s": round(load_s, 1), "peak_gpu_mb": mem.peak_mb,
                    "missing_audio": missing, "per_lang": per_lang, "rows": rows})
    print(f"saved {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
