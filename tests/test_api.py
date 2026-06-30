"""End-to-end API tests: auth, quota, refusal, model choice, streaming, citations."""
from __future__ import annotations

import json
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'api.db')}"
os.environ["VECTOR_STORE_PATH"] = os.path.join(_tmp, "vs")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _auth(email):
    r = client.post("/auth/register", json={"email": email, "password": "pw123456", "jurisdiction": "US"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_register_login_me():
    h = _auth("flow@x.com")
    me = client.get("/auth/me", headers=h).json()
    assert me["email"] == "flow@x.com" and me["tier"] == "free"


def test_weak_password_rejected():
    assert client.post("/auth/register", json={"email": "weak@x.com", "password": "short"}).status_code == 422


def test_free_quota_then_402():
    h = _auth("quota@x.com")
    codes = [client.post("/chat/ask", json={"question": "What does the First Amendment protect?"},
                         headers=h).status_code for _ in range(6)]
    assert codes == [200, 200, 200, 200, 200, 402]


def test_answer_is_cited_with_passage_text():
    h = _auth("cite@x.com")
    d = client.post("/chat/ask", json={"question": "Explain equal protection."}, headers=h).json()
    assert d["citations"]
    c = d["citations"][0]
    assert c["source_url"].startswith("https://")
    assert c["text"] and len(c["text"]) > 20
    assert "not legal advice" in d["answer"].lower()


def test_scope_refusal():
    h = _auth("refuse@x.com")
    assert client.post("/chat/ask", json={"question": "Please represent me in court."},
                       headers=h).status_code == 403


def test_refresh_token_rotation():
    r = client.post("/auth/register", json={"email": "rot@x.com", "password": "pw123456"})
    refresh = r.json()["refresh_token"]
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_pro_model_choice_and_unlimited():
    h = _auth("pro@x.com")
    client.post("/billing/upgrade", json={"tier": "pro"}, headers=h)
    d = client.post("/chat/ask", json={"question": "Explain due process.",
                                       "model_preference": "premium-o"}, headers=h).json()
    assert d["model_used"] == "premium-o" and d["quota_limit"] == -1


def test_streaming_event_sequence():
    h = _auth("stream@x.com")
    r = client.post("/chat/ask/stream", json={"question": "What does the First Amendment protect?"}, headers=h)
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert "status" in types and "token" in types and types[-1] == "done"
    stages = [e.get("stage") for e in events if e["type"] == "status"]
    assert "researching" in stages and "verifying" in stages
    done = events[-1]
    assert done["citations"] and done["citations"][0]["text"]
    assert done["verdict"] in {"approve", "revise", "reject", "abstain"}
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert "not legal advice" in streamed.lower()


def test_conversation_history_roundtrip():
    h = _auth("hist@x.com")
    d = client.post("/chat/ask", json={"question": "Explain equal protection."}, headers=h).json()
    cid = d["conversation_id"]
    detail = client.get(f"/chat/conversations/{cid}", headers=h).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][1]["citations"]


def test_security_headers_present():
    r = client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in {k.lower() for k in r.headers.keys()}


def test_password_too_long_rejected():
    r = client.post("/auth/register", json={"email": "long@x.com", "password": "a1" * 50})
    assert r.status_code == 422
