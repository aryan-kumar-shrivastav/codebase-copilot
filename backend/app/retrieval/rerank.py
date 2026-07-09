"""
Re-rank retrieved chunks before they hit the LLM context window.

Vector search alone over-recalls: it returns the top-k *semantically*
similar chunks, but "similar" and "actually useful for this question"
aren't the same thing, especially with short code snippets where cosine
distance is noisy. A cross-encoder re-rank pass measurably improves
answer quality and is a good eval-chart moment (recall@k before/after).

This ships with a cheap lexical-overlap heuristic so the pipeline runs
with zero extra dependencies; swap `rerank` to call a real cross-encoder
(e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2` via sentence-transformers,
or Voyage's rerank endpoint) for the real quality lift.
"""
from __future__ import annotations

import re

from app.config import settings
from app.models import Chunk


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower()))


def _heuristic_score(query_tokens: set[str], chunk: Chunk) -> float:
    chunk_tokens = _tokenize(chunk.content) | _tokenize(chunk.symbol_name or "") | _tokenize(chunk.file_path)
    if not chunk_tokens:
        return 0.0
    overlap = len(query_tokens & chunk_tokens)
    # small bonus for symbol-name matches — a hit there is a much stronger
    # signal than a hit buried in a function body
    symbol_bonus = 2.0 if query_tokens & _tokenize(chunk.symbol_name or "") else 0.0
    return overlap + symbol_bonus


def rerank(query: str, chunks: list[Chunk], top_n: int | None = None) -> list[Chunk]:
    top_n = top_n or settings.top_k_final
    if not chunks:
        return []
    query_tokens = _tokenize(query)
    scored = [(_heuristic_score(query_tokens, c), c) for c in chunks]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _, c in scored[:top_n]]
