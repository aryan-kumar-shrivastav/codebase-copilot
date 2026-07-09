from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Repo, ChatSession, Message
from app.schemas import ChatRequest, ChatResponse, Citation
from app.agent.graph import run_agent
from app.observability.tracing import Trace

router = APIRouter(prefix="/chat", tags=["chat"])


def _history_for_session(db: Session, session_id: str) -> list[dict]:
    msgs = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    # only user/assistant text turns go back into the LLM history — tool
    # call/result blocks are internal to a single agent run, not persisted
    # as replayable history
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    repo = db.query(Repo).get(req.repo_id)
    if not repo:
        raise HTTPException(404, "repo not found")
    if repo.status != "ready":
        raise HTTPException(409, f"repo is not ready yet (status={repo.status})")

    session = db.query(ChatSession).get(req.session_id) if req.session_id else None
    if not session:
        session = ChatSession(repo_id=repo.id, title=req.message[:60])
        db.add(session)
        db.commit()
        db.refresh(session)

    user_msg = Message(session_id=session.id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()

    trace = Trace(meta={"repo_id": repo.id, "session_id": session.id, "message": req.message})
    history = _history_for_session(db, session.id)[:-1]  # exclude the message we just added

    answer, citations = run_agent(db, repo.id, req.message, history, trace)
    trace_path = trace.save()

    assistant_msg = Message(
        session_id=session.id, role="assistant", content=answer,
        citations=citations, trace_id=trace.trace_id,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        content=answer,
        citations=[Citation(**c) for c in citations],
        trace_id=trace.trace_id,
    )


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, db: Session = Depends(get_db)):
    msgs = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        {"id": m.id, "role": m.role, "content": m.content, "citations": m.citations,
         "trace_id": m.trace_id, "created_at": m.created_at}
        for m in msgs
    ]
