"""
Agent "actions": higher-level operations beyond Q&A. Kept separate from
graph.py because actions have a fixed shape (retrieve -> synthesize
against a template) rather than an open-ended tool loop.

generate_doc is intentionally the safest action to demo: no side effects,
just retrieval + synthesis, and it makes a good showcase for citation
quality since a doc is naturally citation-dense.

propose_fix is stubbed here too — see agent/tools.py:tool_propose_fix for
what's needed before enabling it for real.
"""
from __future__ import annotations

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.prompts import DOC_GENERATION_PROMPT
from app.agent.tools import tool_retrieve
from app.observability.tracing import Trace


def generate_doc(db: Session, repo_id: str, topic: str, trace: Trace) -> tuple[str, list[dict]]:
    with trace.step("retrieve_for_doc", topic=topic):
        chunks = tool_retrieve(db, repo_id, topic)

    if not chunks:
        return f"No relevant code was found for '{topic}' in this repo's index.", []

    context = "\n\n".join(
        f"### {c['file_path']}:{c['start_line']}-{c['end_line']} ({c['symbol_name'] or c['symbol_type']})\n"
        f"```\n{c['content']}\n```"
        for c in chunks
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    with trace.step("llm_call_doc_generation"):
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=1500,
            system=DOC_GENERATION_PROMPT,
            messages=[{"role": "user", "content": f"Topic: {topic}\n\nRetrieved code:\n{context}"}],
        )

    text = "\n".join(b.text for b in response.content if b.type == "text")
    citations = [
        {"chunk_id": c["chunk_id"], "file_path": c["file_path"], "symbol_name": c.get("symbol_name"),
         "start_line": c["start_line"], "end_line": c["end_line"]}
        for c in chunks
    ]
    return text, citations
