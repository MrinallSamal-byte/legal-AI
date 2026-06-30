"""Persistent numpy-backed vector store: real cosine-similarity search over stored
embeddings. Adequate for small/medium corpora and fully offline. For large-scale
production, swap this class for pgvector / Qdrant / Weaviate behind the same interface."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class Record:
    id: str
    text: str
    citation: str
    source_id: str
    source_url: str
    effective_date: str
    keywords: str = ""


class NumpyVectorStore:
    def __init__(self, path: str):
        self.path = path
        self.vectors: np.ndarray | None = None
        self.records: list[Record] = []
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._load()

    @property
    def _vec_file(self) -> str:
        return self.path + ".npy"

    @property
    def _meta_file(self) -> str:
        return self.path + ".json"

    def _load(self) -> None:
        if os.path.exists(self._vec_file) and os.path.exists(self._meta_file):
            self.vectors = np.load(self._vec_file)
            with open(self._meta_file) as f:
                self.records = [Record(**r) for r in json.load(f)]

    def save(self) -> None:
        if self.vectors is not None:
            np.save(self._vec_file, self.vectors)
        with open(self._meta_file, "w") as f:
            json.dump([asdict(r) for r in self.records], f)

    def __len__(self) -> int:
        return len(self.records)

    def replace(self, vectors: np.ndarray, records: list[Record]) -> None:
        self.vectors = vectors.astype(np.float32)
        self.records = records
        self.save()

    def search(self, query_vec: np.ndarray, k: int = 4) -> list[tuple[Record, float]]:
        if self.vectors is None or len(self.records) == 0:
            return []
        sims = self.vectors @ query_vec  # both L2-normalized => cosine similarity
        k = min(k, len(self.records))
        top = np.argsort(-sims)[:k]
        return [(self.records[i], float(sims[i])) for i in top]
