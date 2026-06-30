"""Live government-source connectors: parsing verified offline with a mocked HTTP
transport (the real network calls run on a machine with internet, not in CI)."""
from __future__ import annotations

import os

import httpx
import pytest

from app.rag.live_sources import (CourtListenerSource, FederalRegisterSource,
                                   enabled_source_names)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)


def test_federal_register_parsing():
    def handler(req):
        assert req.url.host == "www.federalregister.gov"
        assert req.url.params.get("conditions[term]") == "wetlands"
        return httpx.Response(200, json={"results": [{
            "title": "Protection of Wetlands", "abstract": "A rule about wetlands.",
            "html_url": "https://www.federalregister.gov/documents/2024/01/02/x",
            "publication_date": "2024-01-02", "document_number": "2024-00001",
            "type": "Rule", "citation": "89 FR 100"}]})
    docs = FederalRegisterSource(_client(handler)).search("wetlands", 5)
    assert len(docs) == 1
    d = docs[0]
    assert d.source_url.startswith("https://www.federalregister.gov/")
    assert d.effective_date == "2024-01-02"
    assert "wetlands" in d.text.lower()
    assert d.citation.startswith("Federal Register")


def test_courtlistener_parsing():
    def handler(req):
        assert req.url.host == "www.courtlistener.com"
        return httpx.Response(200, json={"results": [{
            "caseName": "Roe v. Example", "cluster_id": 4242,
            "snippet": "The court held that ...", "dateFiled": "1999-05-01"}]})
    docs = CourtListenerSource(_client(handler)).search("due process", 5)
    assert docs and docs[0].source_url == "https://www.courtlistener.com/opinion/4242/"
    assert docs[0].citation == "Roe v. Example"


def test_source_failure_is_isolated():
    # A failing source raises; the retriever wraps each in try/except (tested via live_retrieve).
    def handler(req):
        return httpx.Response(500, json={"error": "boom"})
    with pytest.raises(httpx.HTTPStatusError):
        FederalRegisterSource(_client(handler)).search("x", 3)


def test_live_disabled_by_default():
    assert enabled_source_names() == []


def test_live_retrieve_merges(monkeypatch):
    # Enable live sources and inject a mock client; confirm live facts come back ranked.
    from app.config import settings
    from app.rag.retriever import Retriever
    monkeypatch.setattr(settings, "live_sources_enabled", True)
    monkeypatch.setattr(settings, "live_sources", "federal_register")

    def handler(req):
        return httpx.Response(200, json={"results": [{
            "title": "Equal Protection Guidance", "abstract": "Guidance on equal protection.",
            "html_url": "https://www.federalregister.gov/documents/2024/01/02/y",
            "publication_date": "2024-01-02", "document_number": "2024-00002",
            "type": "Notice", "citation": "89 FR 200"}]})
    facts = Retriever().live_retrieve("equal protection", ["equal protection"],
                                      client=_client(handler))
    assert facts and facts[0].id == "fedreg-2024-00002"
    assert facts[0].source_url.startswith("https://www.federalregister.gov/")


@pytest.mark.skipif(not os.environ.get("LIVE_E2E"),
                    reason="set LIVE_E2E=1 to run against the real Federal Register API (needs network)")
def test_real_federal_register_live():
    import app.config as cfg
    cfg.settings.live_sources_enabled = True
    cfg.settings.live_sources = "federal_register"
    from app.rag.retriever import Retriever
    facts = Retriever().live_retrieve("clean water rule", ["clean water"])
    assert facts, "expected real results from the live Federal Register API"
    assert facts[0].source_url.startswith("https://www.federalregister.gov/")
