"""RAG tests: the retriever returns real grounded facts (not mocks) and the right
constitutional provision ranks top for topical queries."""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("VECTOR_STORE_PATH", os.path.join(tempfile.mkdtemp(), "vs"))

from app.rag.retriever import Retriever, chunk_text


def _fresh():
    r = Retriever()
    r.store.vectors = None
    r.store.records = []
    r.ensure_seeded()
    return r


def test_seed_and_retrieve_topical():
    r = _fresh()
    assert not r.is_empty()
    top = r.retrieve("freedom of speech and religion", k=1)
    assert top and top[0].id == "usconst-amend-1"
    assert top[0].source_url.startswith("https://")


def test_equal_protection_query():
    r = _fresh()
    top = r.retrieve("equal protection of the laws", k=1)
    assert top and "14" in top[0].id


def test_chunking_overlap():
    text = " ".join(f"sentence number {i}." for i in range(60))
    chunks = chunk_text(text, max_words=40, overlap=5)
    assert len(chunks) > 1
    assert all(chunks)


def test_offtopic_abstains_ontopic_grounds():
    from app.rag.retriever import is_grounded
    r = _fresh()
    assert is_grounded("What does the First Amendment protect?", r.retrieve("What does the First Amendment protect?", k=3, min_score=0.0))
    assert is_grounded("Explain equal protection.", r.retrieve("Explain equal protection.", k=3, min_score=0.0))
    assert not is_grounded("recipe for chocolate cake", r.retrieve("recipe for chocolate cake", k=3, min_score=0.0))
    assert not is_grounded("best programming language", r.retrieve("best programming language", k=3, min_score=0.0))
