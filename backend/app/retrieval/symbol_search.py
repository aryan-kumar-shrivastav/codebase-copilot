"""
Exact-match search: symbol lookup and grep-style substring search.

Embeddings are bad at "find all callers of `foo()`" — semantic similarity
doesn't guarantee an exact identifier match, and this kind of question has
a single objectively-correct answer set. This module gives the agent a
precise tool for exactly that class of question, used alongside (not
instead of) vector_search.
"""
from __future__ import annotations

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Chunk


def find_symbol(db: Session, repo_id: str, symbol_name: str, limit: int = 20) -> list[Chunk]:
    """Exact + suffix match on qualified symbol name, e.g. "authenticate"
    matches both "authenticate" and "UserService.authenticate"."""
    pattern = f"%{symbol_name}"
    return (
        db.query(Chunk)
        .filter(Chunk.repo_id == repo_id)
        .filter(or_(Chunk.symbol_name == symbol_name, Chunk.symbol_name.like(pattern)))
        .limit(limit)
        .all()
    )


def find_callers(db: Session, repo_id: str, function_name: str, limit: int = 30) -> list[Chunk]:
    """Grep-style search for call sites: any chunk whose content contains
    `function_name(` as a plausible call expression."""
    call_re = re.compile(rf"\b{re.escape(function_name)}\s*\(")
    candidates = (
        db.query(Chunk)
        .filter(Chunk.repo_id == repo_id)
        .filter(Chunk.content.contains(function_name))
        .limit(limit * 4)  # over-fetch, then filter precisely in Python
        .all()
    )
    return [c for c in candidates if call_re.search(c.content)][:limit]


def grep(db: Session, repo_id: str, pattern: str, limit: int = 30) -> list[Chunk]:
    """Raw substring/regex search across chunk content, for anything that
    doesn't fit the symbol/caller shortcuts above."""
    try:
        compiled = re.compile(pattern)
    except re.error:
        compiled = re.compile(re.escape(pattern))
    candidates = (
        db.query(Chunk)
        .filter(Chunk.repo_id == repo_id)
        .limit(2000)  # bounded scan; fine at MVP scale, index full-text for larger repos
        .all()
    )
    return [c for c in candidates if compiled.search(c.content)][:limit]
