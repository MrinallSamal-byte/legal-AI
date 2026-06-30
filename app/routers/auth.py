from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..auth import (consume_email_token, create_access_token, get_current_user,
                    hash_password, issue_email_token, issue_refresh_token,
                    revoke_all_refresh_tokens, rotate_refresh_token, validate_password,
                    verify_password)
from ..config import settings
from ..db import Subscription, User, get_db
from ..email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    jurisdiction: str = "US"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenIn(BaseModel):
    token: str


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _issue(db: Session, user_id: int) -> TokenOut:
    return TokenOut(access_token=create_access_token(user_id),
                    refresh_token=issue_refresh_token(db, user_id))


def _send_verification(db: Session, user: User) -> None:
    raw = issue_email_token(db, user.id, "verify")
    link = f"{settings.app_base_url}/verify?token={raw}"
    send_email(user.email, "Verify your Lexa email",
               f"Welcome to Lexa. Verify your email:\n\n{link}\n\n"
               f"This link expires in {settings.email_token_hours} hours.")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    err = validate_password(body.password)
    if err:
        raise HTTPException(422, err)
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password),
                jurisdiction=body.jurisdiction)
    db.add(user)
    db.flush()
    db.add(Subscription(user_id=user.id, tier="free", status="active"))
    db.commit()
    _send_verification(db, user)
    return _issue(db, user.id)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return _issue(db, user.id)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    user_id, new_refresh = rotate_refresh_token(db, body.refresh_token)
    return TokenOut(access_token=create_access_token(user_id), refresh_token=new_refresh)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_all_refresh_tokens(db, user.id)


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    user_id = consume_email_token(db, body.token, "verify")
    if user_id is None:
        raise HTTPException(400, "Invalid or expired verification token")
    user = db.get(User, user_id)
    user.email_verified = True
    db.commit()
    return {"email_verified": True}


@router.post("/request-verification", status_code=202)
def request_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.email_verified:
        _send_verification(db, user)
    return {"detail": "If your email is unverified, a new link has been sent."}


@router.post("/request-password-reset", status_code=202)
def request_password_reset(body: EmailIn, db: Session = Depends(get_db)):
    # Always 202 regardless, so we don't reveal whether an email is registered.
    user = db.query(User).filter_by(email=body.email).first()
    if user:
        raw = issue_email_token(db, user.id, "reset")
        link = f"{settings.app_base_url}/reset?token={raw}"
        send_email(user.email, "Reset your Lexa password",
                   f"Reset your password:\n\n{link}\n\n"
                   f"This link expires in {settings.email_token_hours} hours. "
                   f"If you didn't request this, ignore this email.")
    return {"detail": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    err = validate_password(body.new_password)
    if err:
        raise HTTPException(422, err)
    user_id = consume_email_token(db, body.token, "reset")
    if user_id is None:
        raise HTTPException(400, "Invalid or expired reset token")
    user = db.get(User, user_id)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    revoke_all_refresh_tokens(db, user.id)  # log out existing sessions after a reset
    return {"detail": "Password updated. Please log in again."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    sub = user.subscription
    return {"email": user.email, "jurisdiction": user.jurisdiction,
            "email_verified": user.email_verified,
            "tier": sub.tier if sub else "free"}
