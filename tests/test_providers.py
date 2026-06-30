"""Provider tests: tolerant JSON extraction and the mock pipeline contract."""
from __future__ import annotations

from app.services.llm_providers import MockProvider, extract_json


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_inline_prose():
    assert extract_json('Sure! {"verdict":"approve","notes":""} done')["verdict"] == "approve"


def test_extract_json_garbage():
    assert extract_json("no json here") == {}


def test_mock_drafter_returns_citations():
    m = MockProvider()
    out = m.complete("oss-flash", "DRAFTER ...", "GROUNDED FACTS:\n[usconst-amend-1] text", json_mode=True)
    data = extract_json(out.text)
    assert "answer" in data and data["cited_ids"]


# --- Live provider adapters (mocked HTTP transport; no network, no keys) ---
import httpx
import pytest

from app.services.llm_providers import LiveProvider


def _provider_with(handler):
    # Skip env-dependent __init__ (proxy env) and inject a clean mock transport.
    p = LiveProvider.__new__(LiveProvider)
    p._client = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    return p


def test_live_anthropic_request_and_parse():
    def handler(req):
        assert req.url.path == "/v1/messages"
        assert "x-api-key" in req.headers and "anthropic-version" in req.headers
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello"}],
                                         "usage": {"input_tokens": 3, "output_tokens": 2}})
    r = _provider_with(handler).complete("premium-a", "sys", "prompt")
    assert r.text == "hello" and r.tokens_in == 3 and r.tokens_out == 2


def test_live_openai_request_and_parse():
    def handler(req):
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["authorization"].startswith("Bearer")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 4}})
    r = _provider_with(handler).complete("mid", "sys", "prompt", json_mode=True)
    assert r.text == "ok" and r.tokens_in == 5 and r.tokens_out == 4


def test_live_google_request_and_parse():
    def handler(req):
        assert "generateContent" in req.url.path
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "yo"}]}}],
                                         "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 1}})
    r = _provider_with(handler).complete("oss-flash", "sys", "prompt")
    assert r.text == "yo" and r.tokens_in == 7 and r.tokens_out == 1


def test_live_retries_then_raises(monkeypatch):
    import app.services.llm_providers as m
    monkeypatch.setattr(m.time, "sleep", lambda *_: None)  # no real backoff in tests
    calls = {"n": 0}
    def handler(req):
        calls["n"] += 1
        return httpx.Response(500, json={"error": "boom"})
    with pytest.raises(RuntimeError):
        _provider_with(handler).complete("mid", "s", "p")
    assert calls["n"] >= 2  # retried before giving up


def test_embedder_factory_defaults_to_hashing():
    from app.rag.embeddings import get_embedder, HashingEmbedder
    assert isinstance(get_embedder(), HashingEmbedder)
