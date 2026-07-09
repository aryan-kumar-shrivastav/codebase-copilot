"""Embedding similarity search over pgvector."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.ingest.embedder import embed_texts
from app.models import Chunk


def vector_search(db: Session, repo_id: str, query: str, k: int | None = None) -> list[Chunk]:
    k = k or settings.top_k_vector
    query_embedding = embed_texts([query])[0]
    return (
        db.query(Chunk)
        .filter(Chunk.repo_id == repo_id)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(k)
        .all()
    )
