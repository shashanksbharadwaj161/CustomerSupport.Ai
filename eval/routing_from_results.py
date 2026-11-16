"""Derive the per-language CPU STT order from measured FLEURS results (no hard-coded winner).

  python -m eval.routing_from_results           # print the proposal
  python -m eval.routing_from_results --write   # write it into agent/engines.json -> stt_cpu.<lang>.order
Rule: measured engines sorted by WER (CER for Japanese) ascending; engines not measured on this machine (e.g. gated
IndicConformer) follow them; Whisper is always present as the last resort. The GPU table ('stt') is not touched:
it must be decided from GPU measurements on the demo PC.
"""
from __future__ import annotations

import argparse
import json

from agent.engines import ENGINES_JSON
from eval.common import OUT

SPEC = {"whisper-small": ("faster-whisper", {"model": "small"}), "whisper-base": ("faster-whisper", {"model": "base"}),
        "mms": ("mms", {}), "indicconformer": ("indicconformer", {"decoding": "rnnt"})}


def proposal() -> dict:
    measured: dict[str, list] = {}
    pending = []
    for f in sorted(OUT.glob("fleurs_stt_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("status") != "measured":
            pending.append(d["engine"])
            continue
        for lang, v in d["per_lang"].items():
            metric = v.get("cer") if lang == "ja" else v.get("wer")
            if metric is not None:
                measured.setdefault(lang, []).append((metric, d["engine"], v["n"], v["latency_median_ms"]))
    out = {}
    for lang, rows in measured.items():
        rows.sort()
        order = [r[1] for r in rows]
        if lang in ("hi", "bn", "kn"):
            order += [p for p in pending if p not in order]
        if not any(o.startswith("whisper") for o in order):
            order.append("whisper-small")
        out[lang] = {"order": order, "evidence": [{"engine": e, "metric": "cer" if lang == "ja" else "wer", "value": m, "n": n,
                                                   "median_ms": ms} for m, e, n, ms in rows]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    p = proposal()
    for lang, v in p.items():
        print(f"{lang}: {' > '.join(v['order'])}   " + ", ".join(f"{e['engine']} {e['metric']}={e['value']} (n={e['n']})" for e in v["evidence"]))
    if a.write and p:
        cfg = json.loads(ENGINES_JSON.read_text(encoding="utf-8"))
        for lang, v in p.items():
            cfg["stt_cpu"][lang] = {"order": [{"engine": SPEC[e][0], "options": SPEC[e][1]} for e in v["order"]],
                                    "_measured": "FLEURS test, CPU, see eval/results.md"}
        ENGINES_JSON.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {ENGINES_JSON}")


if __name__ == "__main__":
    main()
