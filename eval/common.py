"""Shared helpers for M0 runners. Every runner writes eval/out/<name>.json; make_report.py reads them."""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import platform

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
OUT = EVAL / "out"
AUDIO = EVAL / "audio"  # native-speaker recordings: eval/audio/<line_id>.wav (gitignored)
LINES = EVAL / "lines" / "test_lines.jsonl"


def load_lines(langs: list[str] | None = None, include_mixed: bool = True) -> list[dict]:
    rows = [json.loads(l) for l in LINES.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not include_mixed:
        rows = [r for r in rows if r["category"] == "mono"]
    if langs:
        rows = [r for r in rows if r["lang"] in langs]
    return rows


def audio_for(line_id: str, audio_dir: pathlib.Path = AUDIO) -> pathlib.Path | None:
    for ext in (".wav", ".flac", ".webm", ".ogg", ".mp3", ".m4a"):
        p = audio_dir / f"{line_id}{ext}"
        if p.exists():
            return p
    return None


def save(name: str, payload: dict) -> pathlib.Path:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
               "host": platform.node(), **payload}
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load(name: str) -> dict | None:
    p = OUT / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


class GpuMem:
    """Peak GPU memory (torch-allocated) over a block. Returns None without CUDA torch."""

    def __enter__(self):
        self.peak_mb = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
                self._torch = torch
        except Exception:
            self._torch = None
        return self

    def __exit__(self, *exc):
        t = getattr(self, "_torch", None)
        if t is not None:
            self.peak_mb = round(t.cuda.max_memory_allocated() / 2**20)
