"""Account self-service: export all of my data (GDPR/CCPA portability) and delete my
account (erasure). Both operate only on the authenticated user's own data."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import Conversation, Message, UsageLog, User, get_db

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convos = db.query(Conversation).filter_by(user_id=user.id).all()
    convo_ids = [c.id for c in convos]
    msgs = (db.query(Message).filter(Message.conversation_id.in_(convo_ids)).all()
            if convo_ids else [])
    usage = db.query(UsageLog).filter_by(user_id=user.id).all()
    sub = user.subscription
    payload = {
        "profile": {"email": user.email, "jurisdiction": user.jurisdiction,
                    "email_verified": user.email_verified,
                    "created_at": user.created_at.isoformat() if user.created_at else None},
        "subscription": {"tier": sub.tier, "status": sub.status} if sub else None,
        "conversations": [{"id": c.id, "title": c.title,
                           "created_at": c.created_at.isoformat()} for c in convos],
        "messages": [{"conversation_id": m.conversation_id, "role": m.role,
                      "content": m.content, "verdict": m.verdict,
                      "citations": json.loads(m.citations_json or "[]")} for m in msgs],
        "usage": [{"action": u.action_type, "model": u.model_used, "verdict": u.verdict,
                   "cost_estimate": u.cost_estimate,
                   "created_at": u.created_at.isoformat()} for u in usage],
    }
    return Response(content=json.dumps(payload, indent=2), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=lexa-export.json"})


@router.delete("/", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Remove conversation messages first (no relationship cascade on Conversation->Message).
    convo_ids = [c.id for c in db.query(Conversation).filter_by(user_id=user.id).all()]
    if convo_ids:
        db.query(Message).filter(Message.conversation_id.in_(convo_ids)).delete(
            synchronize_session=False)
    # Deleting the user cascades subscription, usage, refresh + email tokens, conversations.
    db.delete(user)
    db.commit()
