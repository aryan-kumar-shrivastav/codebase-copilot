from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Repo
from app.schemas import ActionRequest
from app.agent.actions import generate_doc
from app.agent.tools import tool_propose_fix
from app.observability.tracing import Trace, load_trace

router = APIRouter(tags=["actions"])


@router.post("/actions")
def run_action(req: ActionRequest, db: Session = Depends(get_db)):
    repo = db.query(Repo).get(req.repo_id)
    if not repo:
        raise HTTPException(404, "repo not found")
    if repo.status != "ready":
        raise HTTPException(409, f"repo is not ready yet (status={repo.status})")

    trace = Trace(meta={"repo_id": repo.id, "action": req.action, "instruction": req.instruction})

    if req.action == "generate_doc":
        content, citations = generate_doc(db, repo.id, req.instruction, trace)
        trace_path = trace.save()
        return {"action": req.action, "content": content, "citations": citations, "trace_id": trace.trace_id}

    if req.action == "propose_fix":
        result = tool_propose_fix(db, repo.id, file_path="", description=req.instruction)
        trace.log("action_stub", action=req.action)
        trace.save()
        return {"action": req.action, **result, "trace_id": trace.trace_id}

    raise HTTPException(400, f"unknown action: {req.action}")


@router.get("/traces/{trace_id}")
def get_trace(trace_id: str):
    trace = load_trace(trace_id)
    if not trace:
        raise HTTPException(404, "trace not found")
    return trace
