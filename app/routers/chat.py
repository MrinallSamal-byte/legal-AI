"""Quota-gated legal Q&A: JSON /chat/ask and NDJSON streaming /chat/ask/stream."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import Conversation, Message, User, get_db
from ..logging_config import get_logger
from ..safety import refusal_message, requires_licensed_professional
from ..services.agents import PipelineResult, pipeline_events, run_pipeline
from ..services.llm_providers import get_provider
from ..services.usage import check_quota, log_action, tier_for

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger("lexa.chat")


class AskIn(BaseModel):
    model_config = {"protected_namespaces": ()}
    question: str
    model_preference: str | None = None
    conversation_id: int | None = None


class AskOut(BaseModel):
    model_config = {"protected_namespaces": ()}
    answer: str
    citations: list[dict]
    verdict: str
    model_used: str
    reasoning: str
    conversation_id: int
    quota_used: int
    quota_limit: int


def _precheck(body: AskIn, user: User, db: Session) -> str:
    if not body.question.strip():
        raise HTTPException(422, "Question must not be empty")
    if requires_licensed_professional(body.question):
        raise HTTPException(403, refusal_message())
    allowed, used, limit = check_quota(db, user.id)
    if not allowed:
        raise HTTPException(402, f"Free-tier limit reached ({used}/{limit}). Upgrade for more uses.")
    return tier_for(db, user.id)


def _persist_and_log(db: Session, user: User, body: AskIn, result: PipelineResult) -> int:
    convo = (db.get(Conversation, body.conversation_id) if body.conversation_id else None)
    if convo is None or convo.user_id != user.id:
        convo = Conversation(user_id=user.id, title=body.question[:60])
        db.add(convo)
        db.flush()
    db.add(Message(conversation_id=convo.id, role="user", content=body.question))
    db.add(Message(conversation_id=convo.id, role="assistant", content=result.answer,
                   citations_json=json.dumps(result.citations), verdict=result.verdict))
    db.commit()
    log_action(db, user.id, result.model_used, result.tokens_in, result.tokens_out,
               result.cost_estimate, verdict=result.verdict)
    log.info("answered", extra={"extra_fields": {
        "user": user.id, "verdict": result.verdict, "model": result.model_used,
        "cost": result.cost_estimate}})
    return convo.id


@router.post("/ask", response_model=AskOut)
def ask(body: AskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tier = _precheck(body, user, db)
    result = run_pipeline(provider=get_provider(), question=body.question,
                          jurisdiction=user.jurisdiction, tier_name=tier,
                          preference=body.model_preference)
    convo_id = _persist_and_log(db, user, body, result)
    _, used_after, limit = check_quota(db, user.id)
    return AskOut(answer=result.answer, citations=result.citations, verdict=result.verdict,
                  model_used=result.model_used, reasoning=result.reasoning,
                  conversation_id=convo_id, quota_used=used_after, quota_limit=limit)


@router.post("/ask/stream")
def ask_stream(body: AskIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    tier = _precheck(body, user, db)

    def generate():
        try:
            result: PipelineResult | None = None
            for kind, payload in pipeline_events(
                    provider=get_provider(), question=body.question,
                    jurisdiction=user.jurisdiction, tier_name=tier,
                    preference=body.model_preference):
                if kind == "result":
                    result = payload
                    continue
                yield json.dumps({"type": kind, **payload}) + "\n"

            convo_id = _persist_and_log(db, user, body, result)
            _, used_after, limit = check_quota(db, user.id)
            yield json.dumps({
                "type": "done", "citations": result.citations, "verdict": result.verdict,
                "model_used": result.model_used, "reasoning": result.reasoning,
                "conversation_id": convo_id, "quota_used": used_after, "quota_limit": limit,
            }) + "\n"
        except Exception as exc:  # noqa: BLE001 - surface mid-stream failures to the client
            log.error("stream failed", extra={"extra_fields": {"user": user.id}}, exc_info=exc)
            yield json.dumps({"type": "error",
                              "detail": "Something went wrong while answering. Please retry."}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).filter_by(user_id=user.id).order_by(Conversation.id.desc()).all()
    return [{"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in rows]


@router.get("/conversations/{cid}")
def conversation_detail(cid: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    convo = db.get(Conversation, cid)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    msgs = (db.query(Message).filter_by(conversation_id=cid).order_by(Message.id).all())
    return {"id": convo.id, "title": convo.title,
            "messages": [{"role": m.role, "content": m.content, "verdict": m.verdict,
                          "citations": json.loads(m.citations_json or "[]")} for m in msgs]}
