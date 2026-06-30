"""Pluggable embedding backends.

- HashingEmbedder: dependency-free, deterministic, offline. Real lexical embedding
  (signed feature hashing + L2 norm). Used for tests/demo where no network/model exists.
- SentenceTransformerEmbedder: real semantic embeddings via a local model (production).
- ProviderEmbedder: OpenAI/Google embedding APIs (key-ready, production).

Pick via settings.embeddings_backend. All return L2-normalized float32 vectors so the
vector store can use dot-product == cosine similarity."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import numpy as np

from ..config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> np.ndarray: ...


class HashingEmbedder:
    """Signed feature hashing over unigrams + bigrams. No external dependencies, so it
    runs anywhere and gives stable lexical similarity (good enough to verify the
    retrieval pipeline; use a semantic backend in production)."""

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embeddings_dim

    def _hash(self, token: str) -> tuple[int, float]:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        idx = h % self.dim
        sign = 1.0 if (h >> 7) & 1 else -1.0
        return idx, sign

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, text in enumerate(texts):
            toks = _tokenize(text)
            grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
            for t in grams:
                idx, sign = self._hash(t)
                out[r, idx] += sign * (1.0 / math.sqrt(len(grams) or 1))
            out[r] = _l2(out[r])
        return out


class SentenceTransformerEmbedder:
    """Real semantic embeddings via sentence-transformers (downloads a local model on
    first use). Heavier, but no API cost and high quality."""

    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer  # lazy import
        self.model = SentenceTransformer(model_name or settings.embeddings_model)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return v.astype(np.float32)


class ProviderEmbedder:
    """Embeddings via OpenAI or Google REST APIs (key-ready). Network + key required."""

    def __init__(self, provider: str):
        import httpx  # lazy import
        self._httpx = httpx
        self.provider = provider
        self.dim = 1536 if provider == "openai" else 768

    def embed(self, texts: list[str]) -> np.ndarray:
        if self.provider == "openai":
            r = self._httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": "text-embedding-3-small", "input": texts},
                timeout=settings.request_timeout_seconds,
            )
            r.raise_for_status()
            vecs = [d["embedding"] for d in r.json()["data"]]
        else:  # google
            vecs = []
            for t in texts:
                r = self._httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"text-embedding-004:embedContent?key={settings.google_api_key}",
                    json={"content": {"parts": [{"text": t}]}},
                    timeout=settings.request_timeout_seconds,
                )
                r.raise_for_status()
                vecs.append(r.json()["embedding"]["values"])
        arr = np.array(vecs, dtype=np.float32)
        return np.array([_l2(v) for v in arr], dtype=np.float32)


def get_embedder() -> Embedder:
    b = settings.embeddings_backend
    if b == "sentence_transformers":
        return SentenceTransformerEmbedder()
    if b in ("openai", "google"):
        return ProviderEmbedder(b)
    return HashingEmbedder()
