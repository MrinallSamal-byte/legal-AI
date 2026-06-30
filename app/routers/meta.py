"""Transparency endpoints: show exactly what Lexa is grounded in. Public (no auth) so
users and integrators can audit the sources behind answers."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import TIERS, settings
from ..rag.corpus import SEED_DOCS
from ..rag.live_sources import enabled_source_names

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/sources")
def sources():
    """List the grounded corpus and any enabled live government sources."""
    return {
        "grounded_corpus": [
            {"id": d.id, "citation": d.citation, "source_url": d.source_url,
             "effective_date": d.effective_date}
            for d in SEED_DOCS
        ],
        "corpus_count": len(SEED_DOCS),
        "live_sources": enabled_source_names(),
        "embeddings_backend": settings.embeddings_backend,
        "llm_provider": settings.llm_provider,
    }


@router.get("/tiers")
def tiers():
    """Public tier capabilities (quota, model choice) for pricing/transparency."""
    return {n: {"quota": t.quota, "window_hours": t.window_hours,
                "model_choice": t.allow_model_choice} for n, t in TIERS.items()}
