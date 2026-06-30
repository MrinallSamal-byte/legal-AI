"""Backward-compatibility shim. RAG moved to app/rag/."""
from __future__ import annotations

from ..rag.retriever import GroundedFact, get_retriever, has_sufficient_grounding

__all__ = ["GroundedFact", "get_retriever", "has_sufficient_grounding", "retrieve"]


def retrieve(question: str, jurisdiction: str = "US", k: int = 4):
    return get_retriever().retrieve(question, jurisdiction, k=k)
