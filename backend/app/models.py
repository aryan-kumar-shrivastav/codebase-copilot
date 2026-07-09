"""
ORM models.

Repo         -> one row per ingested codebase
Chunk        -> one row per AST-scoped code chunk, with its embedding
ChatSession  -> one row per conversation
Message      -> one row per turn (user or assistant), assistant turns
                carry citations (chunk ids) and a trace_id for observability
"""
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship

from app.config import settings
from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Repo(Base):
    __tablename__ = "repos"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    source_url = Column(String, nullable=True)     # git remote, if cloned
    local_path = Column(String, nullable=False)     # where it lives on disk
    status = Column(String, default="pending")       # pending|ingesting|ready|error
    commit_sha = Column(String, nullable=True)
    file_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)

    chunks = relationship("Chunk", back_populates="repo", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=_uuid)
    repo_id = Column(String, ForeignKey("repos.id"), nullable=False, index=True)

    file_path = Column(String, nullable=False, index=True)
    symbol_name = Column(String, nullable=True)      # e.g. "UserService.authenticate"
    symbol_type = Column(String, nullable=True)       # function|class|method|module|block
    language = Column(String, nullable=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)

    content = Column(Text, nullable=False)
    # lightweight structural metadata used by symbol_search / re-ranking,
    # e.g. {"imports": [...], "calls": [...], "docstring": "..."}
    meta = Column(JSON, default=dict)

    embedding = Column(Vector(settings.embedding_dims), nullable=True)

    repo = relationship("Repo", back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    repo_id = Column(String, ForeignKey("repos.id"), nullable=False)
    title = Column(String, default="New chat")
    # project-level memory: durable facts the agent has learned about this
    # repo/session, distinct from the per-turn conversation history below
    memory = Column(JSON, default=list)
    created_at = Column(DateTime, default=_now)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user|assistant|tool
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)   # list of chunk ids referenced
    trace_id = Column(String, nullable=True)  # links to observability trace
    created_at = Column(DateTime, default=_now)

    session = relationship("ChatSession", back_populates="messages")
