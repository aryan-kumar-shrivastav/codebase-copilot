"""Pydantic request/response schemas — kept separate from ORM models so the
API contract can evolve independently of the storage layer."""
from datetime import datetime
from pydantic import BaseModel


class IngestRequest(BaseModel):
    source_url: str          # git URL, e.g. https://github.com/org/repo
    name: str | None = None
    branch: str | None = None


class RepoOut(BaseModel):
    id: str
    name: str
    status: str
    file_count: int
    chunk_count: int
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    repo_id: str
    session_id: str | None = None
    message: str


class Citation(BaseModel):
    chunk_id: str
    file_path: str
    symbol_name: str | None
    start_line: int
    end_line: int


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    citations: list[Citation]
    trace_id: str


class ActionRequest(BaseModel):
    repo_id: str
    session_id: str | None = None
    action: str          # "generate_doc" | "propose_fix"
    instruction: str
