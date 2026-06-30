"""Quota checking and usage logging."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import TIERS
from ..db import Subscription, UsageLog, utcnow


def tier_for(db: Session, user_id: int) -> str:
    sub = db.query(Subscription).filter_by(user_id=user_id).one_or_none()
    return sub.tier if sub else "free"


def check_quota(db: Session, user_id: int) -> tuple[bool, int, int]:
    tier = TIERS[tier_for(db, user_id)]
    if tier.quota < 0:
        return True, 0, -1
    window_start = utcnow() - dt.timedelta(hours=tier.window_hours)
    used = (db.query(func.count(UsageLog.id))
            .filter(UsageLog.user_id == user_id, UsageLog.created_at >= window_start)
            .scalar()) or 0
    return used < tier.quota, used, tier.quota


def log_action(db: Session, user_id: int, model_used: str, tokens_in: int, tokens_out: int,
               cost_estimate: float, verdict: str = "", action_type: str = "ask") -> None:
    db.add(UsageLog(user_id=user_id, action_type=action_type, model_used=model_used,
                    verdict=verdict, tokens_in=tokens_in, tokens_out=tokens_out,
                    cost_estimate=cost_estimate))
    db.commit()
