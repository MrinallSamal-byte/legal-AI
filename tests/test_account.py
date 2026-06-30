"""Email verification, password reset, data export, and account deletion."""
from __future__ import annotations

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'acct.db')}"
os.environ["VECTOR_STORE_PATH"] = os.path.join(_tmp, "vs")

from fastapi.testclient import TestClient

import app.email as email_mod
from app.auth import _hash_token
from app.db import EmailToken, SessionLocal, User
from app.main import app

client = TestClient(app)


def _capture_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(email_mod, "send_email",
                        lambda to, subject, body: sent.append((to, subject, body)))
    # routers import send_email by name, so patch there too
    import app.routers.auth as a
    monkeypatch.setattr(a, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def _latest_token(email, purpose):
    db = SessionLocal()
    try:
        uid = db.query(User).filter_by(email=email).first().id
        rows = (db.query(EmailToken).filter_by(user_id=uid, purpose=purpose, used=False)
                .order_by(EmailToken.id.desc()).all())
        return rows[0] if rows else None
    finally:
        db.close()


def _register(email):
    r = client.post("/auth/register", json={"email": email, "password": "pw123456"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_register_sends_verification_and_unverified(monkeypatch):
    sent = _capture_emails(monkeypatch)
    h = _register("verify@x.com")
    assert client.get("/auth/me", headers=h).json()["email_verified"] is False
    assert any("Verify" in s[1] for s in sent)


def test_verify_email_flow(monkeypatch):
    _capture_emails(monkeypatch)
    h = _register("v2@x.com")
    # reproduce the raw token by issuing a fresh one we control
    from app.auth import issue_email_token
    db = SessionLocal()
    uid = db.query(User).filter_by(email="v2@x.com").first().id
    raw = issue_email_token(db, uid, "verify"); db.close()
    assert client.post("/auth/verify-email", json={"token": raw}).json()["email_verified"] is True
    assert client.get("/auth/me", headers=h).json()["email_verified"] is True
    # token is single-use
    assert client.post("/auth/verify-email", json={"token": raw}).status_code == 400


def test_password_reset_flow(monkeypatch):
    _capture_emails(monkeypatch)
    _register("reset@x.com")
    # request reset is always 202, even for unknown emails (no enumeration)
    assert client.post("/auth/request-password-reset", json={"email": "reset@x.com"}).status_code == 202
    assert client.post("/auth/request-password-reset", json={"email": "nope@x.com"}).status_code == 202
    from app.auth import issue_email_token
    db = SessionLocal()
    uid = db.query(User).filter_by(email="reset@x.com").first().id
    raw = issue_email_token(db, uid, "reset"); db.close()
    assert client.post("/auth/reset-password", json={"token": raw, "new_password": "newpass99"}).status_code == 200
    # old password rejected, new password works
    assert client.post("/auth/login", json={"email": "reset@x.com", "password": "pw123456"}).status_code == 401
    assert client.post("/auth/login", json={"email": "reset@x.com", "password": "newpass99"}).status_code == 200


def test_export_and_delete(monkeypatch):
    _capture_emails(monkeypatch)
    h = _register("data@x.com")
    client.post("/chat/ask", json={"question": "Explain equal protection."}, headers=h)
    exp = client.get("/account/export", headers=h)
    assert exp.status_code == 200
    body = exp.json()
    assert body["profile"]["email"] == "data@x.com"
    assert len(body["messages"]) >= 2 and len(body["conversations"]) >= 1
    # delete account -> subsequent auth fails
    assert client.delete("/account/", headers=h).status_code == 204
    assert client.get("/auth/me", headers=h).status_code == 401
