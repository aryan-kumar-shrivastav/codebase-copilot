"""
Thin embedding-provider abstraction so swapping OpenAI <-> Voyage (or
anything else) is a one-line config change, not a refactor.

Worth A/B testing both for a code-RAG project: Voyage's `voyage-code-2`
is trained specifically on code and typically beats general-purpose text
embedding models on retrieval-quality benchmarks for this domain — a good
concrete comparison to write up.
"""
from __future__ import annotations

import httpx

from app.config import settings


class EmbeddingError(RuntimeError):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embedding_provider == "openai":
        return _embed_openai(texts)
    if settings.embedding_provider == "voyage":
        return _embed_voyage(texts)
    raise EmbeddingError(f"Unknown embedding_provider: {settings.embedding_provider}")


def _embed_openai(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        raise EmbeddingError("OPENAI_API_KEY is not set")
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": settings.embedding_model, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    # API returns items possibly out of order; sort by index to be safe
    data.sort(key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def _embed_voyage(texts: list[str]) -> list[list[float]]:
    if not settings.voyage_api_key:
        raise EmbeddingError("VOYAGE_API_KEY is not set")
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
        json={"model": "voyage-code-2", "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    return [d["embedding"] for d in resp.json()["data"]]
