"""M0 cross-lingual retrieval: BGE-M3 dense embeddings, English knowledge chunks, queries in
all 5 languages (the test lines). Reports hit@1 and hit@3 per language.

  python -m eval.runners.run_retrieval
"""
from __future__ import annotations

import argparse
import json
import time

from eval.common import EVAL, GpuMem, load_lines, save


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="BAAI/bge-m3")
    a = ap.parse_args(argv)

    import numpy as np
    from sentence_transformers import SentenceTransformer

    chunks = [json.loads(l) for l in (EVAL / "fixtures" / "kb_chunks.jsonl").read_text().splitlines() if l]
    topics = {c["topic"] for c in chunks}
    queries = [l for l in load_lines() if l["topic"] in topics]
    with GpuMem() as mem:
        t0 = time.perf_counter()
        model = SentenceTransformer(a.model)
        load_s = time.perf_counter() - t0
        C = model.encode([c["text"] for c in chunks], normalize_embeddings=True)
        t = time.perf_counter()
        Q = model.encode([q["text"] for q in queries], normalize_embeddings=True)
        q_ms = (time.perf_counter() - t) * 1000 / len(queries)
    sims = Q @ C.T
    rows = []
    for q, s in zip(queries, sims):
        order = np.argsort(-s)
        got = [chunks[i]["topic"] for i in order[:3]]
        rows.append({"id": q["id"], "lang": q["lang"], "category": q["category"], "topic": q["topic"],
                     "top3": got, "top1_score": round(float(s[order[0]]), 3),
                     "hit1": got[0] == q["topic"], "hit3": q["topic"] in got})
    per_lang = {}
    for lang in sorted({r["lang"] for r in rows}):
        rs = [r for r in rows if r["lang"] == lang and r["category"] == "mono"]
        if rs:
            per_lang[lang] = {"n": len(rs), "hit1": round(sum(r["hit1"] for r in rs) / len(rs), 3),
                              "hit3": round(sum(r["hit3"] for r in rs) / len(rs), 3)}
    mixed = [r for r in rows if r["category"] != "mono"]
    p = save("retrieval", {"kind": "retrieval", "model": a.model, "load_s": round(load_s, 1),
                           "query_ms": round(q_ms, 1), "peak_gpu_mb": mem.peak_mb,
                           "per_lang": per_lang,
                           "mixed": {"n": len(mixed), "hit1": round(sum(r["hit1"] for r in mixed) / len(mixed), 3) if mixed else None},
                           "rows": rows})
    for lang, v in per_lang.items():
        print(lang, v)
    print(f"saved {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
