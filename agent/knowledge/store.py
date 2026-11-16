"""Vector store: Chroma (local, telemetry off), one collection per knowledge source."""
from __future__ import annotations

import pathlib

import numpy as np


class VectorStore:
    def __init__(self, path: pathlib.Path):
        import chromadb
        from chromadb.config import Settings

        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False, allow_reset=False))

    @staticmethod
    def _name(source_id: str) -> str:
        return "src_" + "".join(c if c.isalnum() else "_" for c in source_id)[:60]

    def replace(self, source_id: str, ids: list[str], vecs: np.ndarray, docs: list[str], metas: list[dict]) -> None:
        self.delete(source_id)
        col = self.client.create_collection(self._name(source_id), metadata={"hnsw:space": "cosine"})
        for i in range(0, len(ids), 256):
            col.add(ids=ids[i:i + 256], embeddings=vecs[i:i + 256].tolist(), documents=docs[i:i + 256], metadatas=metas[i:i + 256])

    def query(self, source_id: str, vec: np.ndarray, k: int) -> list[dict]:
        try:
            col = self.client.get_collection(self._name(source_id))
        except Exception:
            return []
        n = min(k, col.count())
        if n == 0:
            return []
        r = col.query(query_embeddings=[vec.tolist()], n_results=n)
        out = []
        for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
            out.append({"text": doc, "url": meta.get("url"), "title": meta.get("title"), "heading": meta.get("heading"),
                        "score": round(1 - float(dist), 4), "source_id": source_id})
        return out

    def peek(self, source_id: str, limit: int = 20) -> list[dict]:
        try:
            col = self.client.get_collection(self._name(source_id))
        except Exception:
            return []
        r = col.get(limit=limit)
        return [{"id": i, "text": d, **m} for i, d, m in zip(r["ids"], r["documents"], r["metadatas"])]

    def delete(self, source_id: str) -> None:
        try:
            self.client.delete_collection(self._name(source_id))
        except Exception:
            pass
