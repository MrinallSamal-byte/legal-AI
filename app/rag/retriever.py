"""Retrieval pipeline: chunk, embed (text enriched with citation + topical keywords),
index, retrieve, and decide whether there is *sufficient grounding* to answer at all.

The grounding decision is what lets Lexa abstain on off-topic questions instead of
forcing an answer out of unrelated passages."""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from ..config import settings
from .corpus import SEED_DOCS
from .embeddings import get_embedder
from .store import NumpyVectorStore, Record

_STOP = {
    "what", "does", "do", "the", "a", "an", "is", "are", "was", "were", "of", "to", "in",
    "on", "and", "or", "for", "with", "that", "this", "my", "how", "can", "could", "would",
    "should", "when", "where", "which", "who", "whom", "about", "into", "under", "law",
    "laws", "legal", "mean", "means", "explain", "tell", "give", "need", "want", "please",
}


def _content_terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{4,}", (text or "").lower()) if t not in _STOP}


@dataclass
class GroundedFact:
    id: str
    text: str
    citation: str
    source_id: str
    source_url: str
    effective_date: str
    keywords: str = ""
    score: float = 0.0


def chunk_text(text: str, max_words: int = 120, overlap: int = 25) -> list[str]:
    sentences = re.split(r"(?<=[.;:])\s+", text.strip())
    chunks, cur, count = [], [], 0
    for s in sentences:
        w = len(s.split())
        if count + w > max_words and cur:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []
            count = sum(len(x.split()) for x in cur)
        cur.append(s)
        count += w
    if cur:
        chunks.append(" ".join(cur))
    return chunks or [text]


class Retriever:
    def __init__(self):
        self.embedder = get_embedder()
        self.store = NumpyVectorStore(settings.vector_store_path)

    def is_empty(self) -> bool:
        return len(self.store) == 0

    def build_index(self, docs: list[Record]) -> int:
        """Chunk, then embed each chunk enriched with its citation + topical keywords so
        natural-language questions retrieve the right provision. The stored/displayed text
        stays the verbatim passage."""
        records: list[Record] = []
        embed_texts: list[str] = []
        for d in docs:
            chunks = chunk_text(d.text)
            kw = getattr(d, "keywords", "") or ""
            for i, ch in enumerate(chunks):
                rid = d.id if len(chunks) == 1 else f"{d.id}#chunk{i}"
                records.append(Record(id=rid, text=ch, citation=d.citation,
                                      source_id=d.source_id, source_url=d.source_url,
                                      effective_date=d.effective_date, keywords=kw))
                embed_texts.append(f"{d.citation}. {kw}. {ch}")
        vectors = self.embedder.embed(embed_texts)
        self.store.replace(vectors, records)
        return len(records)

    def ensure_seeded(self) -> None:
        if self.is_empty():
            self.build_index(SEED_DOCS)

    def retrieve(self, question: str, jurisdiction: str = "US", k: int = 4,
                 min_score: float | None = None) -> list[GroundedFact]:
        self.ensure_seeded()
        floor = settings.grounding_floor if min_score is None else min_score
        qvec = self.embedder.embed([question])[0].astype(np.float32)
        hits = self.store.search(qvec, k=k)
        return [GroundedFact(id=r.id, text=r.text, citation=r.citation, source_id=r.source_id,
                             source_url=r.source_url, effective_date=r.effective_date,
                             keywords=getattr(r, 'keywords', ''), score=round(s, 4))
                for r, s in hits if s >= floor]


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def has_sufficient_grounding(facts: list[GroundedFact]) -> bool:
    """Legacy len-based check (kept for the back-compat shim)."""
    return len(facts) > 0


def is_grounded(question: str, facts: list[GroundedFact]) -> bool:
    """Decide whether retrieved facts are strong enough to answer, else abstain.

    Rule: need a non-empty result whose top score clears the floor; if the top score is
    merely mediocre (below `grounding_strong`), also require that the question shares at
    least one meaningful content word with the retrieved passages. This filters off-topic
    questions (no shared vocabulary) while still answering on-topic paraphrases that score
    well. With a semantic embedder the score gap widens and this becomes even cleaner."""
    if not facts:
        return False
    top = facts[0].score
    if top < settings.grounding_floor:
        return False
    # The offline lexical (hashing) embedder gives false-friend matches, so always require
    # a real shared term there. A semantic embedder is trustworthy on score alone.
    lexical = settings.embeddings_backend == "hashing"
    if not lexical and top >= settings.grounding_strong:
        return True
    qterms = _content_terms(question)
    if not qterms:
        return True
    blob = " ".join(f"{f.citation} {f.keywords} {f.text}" for f in facts).lower()
    return any(t in blob for t in qterms)
