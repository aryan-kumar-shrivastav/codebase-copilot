from __future__ import annotations

import os

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Repo
from app.schemas import IngestRequest, RepoOut
from app.ingest.pipeline import clone_repo, run_ingest

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("", response_model=RepoOut, status_code=202)
def ingest_repo(req: IngestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    name = req.name or req.source_url.rstrip("/").split("/")[-1].removesuffix(".git")
    local_path = os.path.join(settings.sandbox_repo_root, name)

    repo = Repo(name=name, source_url=req.source_url, local_path=local_path, status="pending")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    def _do_ingest():
        # each background task needs its own db session — the request-scoped
        # one from Depends(get_db) is closed by the time this runs
        from app.db import SessionLocal
        bg_db = SessionLocal()
        try:
            bg_repo = bg_db.query(Repo).get(repo.id)
            bg_repo.commit_sha = clone_repo(req.source_url, local_path, req.branch)
            bg_db.commit()
            run_ingest(bg_db, bg_repo)
        finally:
            bg_db.close()

    background_tasks.add_task(_do_ingest)
    return repo


@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db)):
    return db.query(Repo).order_by(Repo.created_at.desc()).all()


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repo).get(repo_id)
    if not repo:
        raise HTTPException(404, "repo not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repo(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repo).get(repo_id)
    if not repo:
        raise HTTPException(404, "repo not found")
    db.delete(repo)
    db.commit()
