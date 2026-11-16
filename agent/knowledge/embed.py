"""Embedders. BGE-M3 (MIT, multilingual) when installed + downloaded; otherwise a LEXICAL hashing fallback
that is clearly labelled (it cannot match across languages)."""
from __future__ import annotations

import hashlib
import math
import os
import re

import numpy as np


class HashEmbedder:
    name = "lexical-hash (fallback: no cross-lingual matching)"
    dim = 1024

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            t = re.sub(r"\s+", " ", t.lower())
            toks = re.findall(r"\w+", t)
            feats = toks + [t[j:j + 4] for j in range(max(0, len(t) - 3))]
            for f in feats:
                h = int(hashlib.md5(f.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0 if f in toks else 0.3
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


class BGEM3Embedder:
    name = "BAAI/bge-m3"

    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("BAAI/bge-m3")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True, batch_size=16), dtype=np.float32)


_cache: dict[str, object] = {}


def bge_available() -> bool:
    try:
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is None:
            return False
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache("BAAI/bge-m3", "config.json"), str)
    except Exception:
        return False


def get_embedder(kind: str | None = None):
    kind = kind or os.environ.get("SHAON_EMBEDDER") or "auto"
    if kind == "auto":
        kind = "bge-m3" if bge_available() else "hash"
    if kind not in _cache:
        _cache[kind] = BGEM3Embedder() if kind == "bge-m3" else HashEmbedder()
    return _cache[kind]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    d = float(np.dot(a, b))
    return d if not math.isnan(d) else 0.0
