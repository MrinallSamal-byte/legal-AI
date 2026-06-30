"""Subscription management. /upgrade is a DEV stub - replace with Stripe webhook."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import TIERS
from ..db import Subscription, User, get_db

router = APIRouter(prefix="/billing", tags=["billing"])


class UpgradeIn(BaseModel):
    tier: str


@router.get("/tiers")
def list_tiers():
    return {n: {"quota": t.quota, "window_hours": t.window_hours,
                "default_model": t.default_model, "model_choice": t.allow_model_choice}
            for n, t in TIERS.items()}


@router.post("/upgrade")
def upgrade(body: UpgradeIn, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    if body.tier not in ("free", "plus", "pro"):
        raise HTTPException(400, "tier must be free, plus, or pro")
    sub = db.query(Subscription).filter_by(user_id=user.id).one()
    sub.tier = body.tier
    db.commit()
    return {"tier": sub.tier, "note": "DEV stub - wire to Stripe webhook for real billing"}
