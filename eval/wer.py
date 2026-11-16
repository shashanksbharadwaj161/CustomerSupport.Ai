"""WER / CER with per-language normalization (no external deps).

- Japanese has no spaces: report CER only (WER is not meaningful).
- Indic scripts: WER on whitespace tokens + CER (CER is more forgiving of agglutination).
- Normalization: NFC, lowercase Latin, drop punctuation/symbols (incl. danda), collapse spaces.
"""
from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            out.append(" ")
        elif ch in "‌‍":  # ZWNJ/ZWJ: rendering hints, not content
            continue
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> tuple[int, int]:
    """(errors, reference words)."""
    r, h = normalize(ref).split(), normalize(hyp).split()
    return edit_distance(r, h), len(r)


def cer(ref: str, hyp: str) -> tuple[int, int]:
    """(errors, reference chars), spaces removed."""
    r, h = list(normalize(ref).replace(" ", "")), list(normalize(hyp).replace(" ", ""))
    return edit_distance(r, h), len(r)


def score(lang: str, ref: str, hyp: str) -> dict:
    ce, cn = cer(ref, hyp)
    d = {"cer_err": ce, "cer_n": cn}
    if lang != "ja":
        we, wn = wer(ref, hyp)
        d.update(wer_err=we, wer_n=wn)
    return d


def aggregate(scores: list[dict]) -> dict:
    """Corpus-level rates (sum errors / sum reference length)."""
    out = {}
    for k in ("wer", "cer"):
        n = sum(s.get(f"{k}_n", 0) for s in scores)
        if n:
            out[k] = round(sum(s.get(f"{k}_err", 0) for s in scores) / n, 4)
    return out
