"""Password hashing, JWT access tokens, opaque refresh tokens, current-user dependency."""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .db import EmailToken, RefreshToken, User, get_db, utcnow

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=True)


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)


def validate_password(p: str) -> str | None:
    if len(p) < settings.min_password_length:
        return f"Password must be at least {settings.min_password_length} characters."
    if len(p.encode("utf-8")) > settings.max_password_length:
        return f"Password must be at most {settings.max_password_length} bytes."
    if p.isalpha() or p.isdigit():
        return "Password must include both letters and numbers."
    return None


def create_access_token(user_id: int) -> str:
    expire = utcnow() + dt.timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "access"},
                      settings.jwt_secret, algorithm=settings.jwt_alg)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh_token(db: Session, user_id: int) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(RefreshToken(
        user_id=user_id, token_hash=_hash_token(raw), revoked=False,
        expires_at=utcnow() + dt.timedelta(days=settings.refresh_token_days),
    ))
    db.commit()
    return raw


def rotate_refresh_token(db: Session, raw: str) -> tuple[int, str]:
    row = db.query(RefreshToken).filter_by(token_hash=_hash_token(raw), revoked=False).first()
    if not row or row.expires_at.replace(tzinfo=dt.timezone.utc) < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    row.revoked = True
    db.commit()
    new_raw = issue_refresh_token(db, row.user_id)
    return row.user_id, new_raw


def revoke_all_refresh_tokens(db: Session, user_id: int) -> None:
    db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).update({"revoked": True})
    db.commit()


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        if payload.get("type") != "access":
            raise cred_exc
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise cred_exc
    user = db.get(User, user_id)
    if user is None:
        raise cred_exc
    return user


def issue_email_token(db: Session, user_id: int, purpose: str) -> str:
    """Create a single-use, expiring token for email verification or password reset."""
    raw = secrets.token_urlsafe(48)
    db.add(EmailToken(
        user_id=user_id, token_hash=_hash_token(raw), purpose=purpose, used=False,
        expires_at=utcnow() + dt.timedelta(hours=settings.email_token_hours),
    ))
    db.commit()
    return raw


def consume_email_token(db: Session, raw: str, purpose: str) -> int | None:
    """Validate + burn a token. Returns user_id on success, else None."""
    row = (db.query(EmailToken)
           .filter_by(token_hash=_hash_token(raw), purpose=purpose, used=False)
           .first())
    if not row or row.expires_at.replace(tzinfo=dt.timezone.utc) < utcnow():
        return None
    row.used = True
    db.commit()
    return row.user_id
