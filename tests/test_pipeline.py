"""Pipeline tests: grounded, cited, disclaimed answers and tier-aware model choice."""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("VECTOR_STORE_PATH", os.path.join(tempfile.mkdtemp(), "vs"))

from app.services.agents import run_pipeline
from app.services.llm_providers import MockProvider


def test_pipeline_grounded_and_cited():
    res = run_pipeline(MockProvider(), "What does the First Amendment protect?", "US", "free")
    assert res.answer
    assert "not legal advice" in res.answer.lower()
    assert res.citations and res.citations[0]["source_url"].startswith("https://")
    assert res.verdict in {"approve", "revise", "reject"}
    assert not res.abstained
    assert res.reasoning  # the drafter exposes its step-by-step reasoning


def test_pro_tier_model_choice():
    res = run_pipeline(MockProvider(), "Explain equal protection.", "US", "pro",
                       preference="premium-o")
    assert res.model_used in {"premium-o", "premium-a"}


if __name__ == "__main__":
    test_pipeline_grounded_and_cited()
    test_pro_tier_model_choice()
    print("OK: pipeline tests passed")


def test_offtopic_question_abstains():
    res = run_pipeline(MockProvider(), "recipe for chocolate cake", "US", "free")
    assert res.abstained and res.verdict == "abstain"
    assert not res.citations
    assert "couldn't find authoritative support" in res.answer.lower()
