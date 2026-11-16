"""google/fleurs (CC-BY-4.0) test-split sampler for real-audio STT / language-ID evaluation.

FLEURS is a script-based dataset that current `datasets` releases no longer execute, so we read its raw files:
data/<config>/test.tsv (transcripts) + data/<config>/audio/test.tar.gz, STREAMED over HTTP: the tarball is never stored;
only the sampled clips are kept, resampled to 16 kHz mono WAV, in a cache OUTSIDE the repo (default
~/.cache/shaon-eval/fleurs, capped at 2 GB). Never commit audio.

Attribution: FLEURS, Conneau et al. 2022, "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech",
https://huggingface.co/datasets/google/fleurs, licensed CC-BY-4.0.
Caveat: clean, read, Wikipedia-style sentences - NOT phone calls; error rates here are optimistic for live calls.
"""
from __future__ import annotations

import csv
import io
import json
import os
import pathlib
import random
import subprocess
import tarfile

import requests

BASE = "https://huggingface.co/datasets/google/fleurs/resolve/main/data"
CONFIGS = {"hi": "hi_in", "bn": "bn_in", "kn": "kn_in", "ja": "ja_jp", "en": "en_us"}
CACHE = pathlib.Path(os.environ.get("SHAON_EVAL_CACHE") or pathlib.Path.home() / ".cache" / "shaon-eval") / "fleurs"
CAP_BYTES = 2 * 1024**3
SEED = 20261116


def cache_size(root: pathlib.Path = CACHE) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def _rows(cfg: str) -> list[dict]:
    r = requests.get(f"{BASE}/{cfg}/test.tsv", timeout=60)
    r.raise_for_status()
    rows = []
    for row in csv.reader(io.StringIO(r.text), delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(row) >= 4:
            rows.append({"sid": row[0], "file": row[1], "raw": row[2], "norm": row[3],
                         "gender": row[6] if len(row) > 6 else None})
    return rows


def sample(lang: str, n: int, seed: int = SEED) -> list[dict]:
    """Deterministic sample: one recording per distinct sentence, then `n` sentences by seeded shuffle."""
    cfg = CONFIGS[lang]
    rows = _rows(cfg)
    by_sid: dict[str, dict] = {}
    for row in rows:
        by_sid.setdefault(row["sid"], row)
    sids = sorted(by_sid)
    random.Random(f"{seed}:{lang}").shuffle(sids)
    return [by_sid[s] for s in sids[:n]]


def fetch(lang: str, n: int, seed: int = SEED) -> list[dict]:
    """Return up to n clips {id, lang, wav, text, norm, seconds}; streams the tarball only if clips are missing."""
    out_dir = CACHE / CONFIGS[lang]
    out_dir.mkdir(parents=True, exist_ok=True)
    want = sample(lang, n, seed)
    missing = {w["file"]: w for w in want if not (out_dir / (w["file"][:-4] + ".16k.wav")).exists()}
    if missing:
        if cache_size() > CAP_BYTES:
            raise RuntimeError(f"FLEURS cache over 2 GB cap: {CACHE}")
        with requests.get(f"{BASE}/{CONFIGS[lang]}/audio/test.tar.gz", stream=True, timeout=120) as r:
            r.raise_for_status()
            r.raw.decode_content = True
            with tarfile.open(fileobj=r.raw, mode="r|gz") as tar:
                for m in tar:
                    base = os.path.basename(m.name)
                    if base in missing:
                        data = tar.extractfile(m).read()
                        dst = out_dir / (base[:-4] + ".16k.wav")
                        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                                        "-sample_fmt", "s16", str(dst)], input=data, check=True)
                        missing.pop(base)
                        if not missing:
                            break  # stop streaming: the rest of the archive is never downloaded
    clips = []
    import soundfile as sf
    for w in want:
        p = out_dir / (w["file"][:-4] + ".16k.wav")
        if p.exists():
            clips.append({"id": f"{lang}_{w['file'][:-4]}", "lang": lang, "wav": str(p), "text": w["raw"], "norm": w["norm"],
                          "seconds": round(sf.info(str(p)).duration, 2), "gender": w["gender"]})
    (out_dir / f"manifest_seed{seed}.json").write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    return clips


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    for lang in (sys.argv[2:] or list(CONFIGS)):
        c = fetch(lang, n)
        print(lang, len(c), "clips", round(sum(x["seconds"] for x in c) / 60, 1), "min")
    print("cache", round(cache_size() / 1e6, 1), "MB at", CACHE)
