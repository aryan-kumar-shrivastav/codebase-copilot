"""
Tools the agent can call. Each tool takes the db session + repo_id as
fixed context (bound via functools.partial when the graph is built) plus
whatever the LLM decides to pass, and returns plain data — formatting for
the LLM happens in graph.py so tools stay unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.models import Chunk
from app.retrieval.vector_search import vector_search
from app.retrieval.symbol_search import find_symbol, find_callers, grep
from app.retrieval.rerank import rerank


def _chunk_to_dict(c: Chunk) -> dict:
    return {
        "chunk_id": c.id,
        "file_path": c.file_path,
        "symbol_name": c.symbol_name,
        "symbol_type": c.symbol_type,
        "start_line": c.start_line,
        "end_line": c.end_line,
        "content": c.content,
    }


def tool_retrieve(db: Session, repo_id: str, query: str) -> list[dict]:
    """Semantic retrieval: embed the query, pull top-k by cosine similarity,
    then re-rank down to the final set actually shown to the LLM."""
    candidates = vector_search(db, repo_id, query)
    top = rerank(query, candidates)
    return [_chunk_to_dict(c) for c in top]


def tool_find_symbol(db: Session, repo_id: str, symbol_name: str) -> list[dict]:
    """Exact symbol lookup — use when the user names a specific function/class/method."""
    return [_chunk_to_dict(c) for c in find_symbol(db, repo_id, symbol_name)]


def tool_find_callers(db: Session, repo_id: str, function_name: str) -> list[dict]:
    """Find call sites of a function — precise, not semantic, by design."""
    return [_chunk_to_dict(c) for c in find_callers(db, repo_id, function_name)]


def tool_grep(db: Session, repo_id: str, pattern: str) -> list[dict]:
    """Raw pattern search across the indexed codebase."""
    return [_chunk_to_dict(c) for c in grep(db, repo_id, pattern)]


def tool_propose_fix(db: Session, repo_id: str, file_path: str, description: str) -> dict:
    """
    STUB — real implementation would:
      1. Fetch current file content from the cloned repo on disk
      2. Ask the LLM for a unified diff constrained to that file
      3. Apply the diff in a scratch branch, run the project's test suite
         in a sandboxed container, and only proceed if it passes
      4. Push the branch and open a draft PR via the GitHub API
    Wiring point kept separate from Q&A tools because it has real side
    effects (a written diff, a PR, CI usage) and needs the sandbox/test-
    runner infra described in the README before it's safe to enable.
    """
    return {
        "status": "not_implemented",
        "note": (
            "propose_fix is a stub. Wire this to a git worktree + sandboxed "
            "test runner before enabling — see README 'Extending: PR actions'."
        ),
        "file_path": file_path,
        "requested_change": description,
    }


TOOL_SCHEMAS = [
    {
        "name": "retrieve",
        "description": "Semantic search over the codebase for relevant code chunks. Use for conceptual/'how does X work' questions.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "find_symbol",
        "description": "Look up a specific function, class, or method by name. Use when the user names a symbol directly.",
        "input_schema": {
            "type": "object",
            "properties": {"symbol_name": {"type": "string"}},
            "required": ["symbol_name"],
        },
    },
    {
        "name": "find_callers",
        "description": "Find all call sites of a function. Use for 'who calls X' / impact-analysis questions.",
        "input_schema": {
            "type": "object",
            "properties": {"function_name": {"type": "string"}},
            "required": ["function_name"],
        },
    },
    {
        "name": "grep",
        "description": "Raw substring/regex search across the codebase. Use as a fallback when retrieve/find_symbol don't fit.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
]
