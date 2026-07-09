"""
Agent orchestration via LangGraph.

State machine: agent decides to call a tool -> tool runs -> result goes
back to agent -> repeat until the agent emits a final answer (or hits
max_agent_steps). Every step is written to a Trace so the whole run is
inspectable afterward from the observability layer.

Deliberately built on the raw Anthropic SDK (not a LangChain chat model
wrapper) so the tool-calling loop is fully visible and easy to reason
about — LangGraph is used for the state machine, not to hide the LLM call.
"""
from __future__ import annotations

import json
from typing import Annotated, TypedDict

import anthropic
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import (
    TOOL_SCHEMAS, tool_retrieve, tool_find_symbol, tool_find_callers, tool_grep,
)
from app.observability.tracing import Trace

TOOL_DISPATCH = {
    "retrieve": lambda db, repo_id, args: tool_retrieve(db, repo_id, args["query"]),
    "find_symbol": lambda db, repo_id, args: tool_find_symbol(db, repo_id, args["symbol_name"]),
    "find_callers": lambda db, repo_id, args: tool_find_callers(db, repo_id, args["function_name"]),
    "grep": lambda db, repo_id, args: tool_grep(db, repo_id, args["pattern"]),
}


class AgentState(TypedDict):
    repo_id: str
    messages: list[dict]        # Anthropic-format message list, grows each turn
    citations: Annotated[list[dict], lambda a, b: a + b]  # accumulated chunk refs
    steps_taken: int
    final_answer: str | None


def build_graph(db: Session, trace: Trace):
    """Returns a compiled LangGraph app bound to this db session/trace.
    Rebuilding per-request is cheap and keeps the db session lifetime
    correctly scoped to the request."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def call_model(state: AgentState) -> AgentState:
        with trace.step("llm_call", step_number=state["steps_taken"]):
            response = client.messages.create(
                model=settings.llm_model,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=state["messages"],
            )

        new_messages = state["messages"] + [{"role": "assistant", "content": response.content}]

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses or state["steps_taken"] + 1 >= settings.max_agent_steps:
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return {
                **state,
                "messages": new_messages,
                "steps_taken": state["steps_taken"] + 1,
                "final_answer": "\n".join(text_blocks).strip() or "I couldn't find a confident answer in the codebase.",
            }

        return {**state, "messages": new_messages, "steps_taken": state["steps_taken"] + 1}

    def call_tools(state: AgentState) -> AgentState:
        last_message = state["messages"][-1]
        tool_uses = [b for b in last_message["content"] if getattr(b, "type", None) == "tool_use"]

        tool_results = []
        new_citations = []
        for tu in tool_uses:
            handler = TOOL_DISPATCH.get(tu.name)
            with trace.step("tool_call", tool=tu.name, args=tu.input):
                result = handler(db, state["repo_id"], tu.input) if handler else {"error": "unknown tool"}

            if isinstance(result, list):
                new_citations.extend([
                    {"chunk_id": r["chunk_id"], "file_path": r["file_path"],
                     "symbol_name": r.get("symbol_name"), "start_line": r["start_line"],
                     "end_line": r["end_line"]}
                    for r in result if "chunk_id" in r
                ])

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result)[:8000],  # keep context bounded
            })

        return {
            **state,
            "messages": state["messages"] + [{"role": "user", "content": tool_results}],
            "citations": new_citations,
        }

    def route(state: AgentState) -> str:
        return END if state.get("final_answer") else "tools"

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def run_agent(db: Session, repo_id: str, user_message: str, history: list[dict] | None,
              trace: Trace) -> tuple[str, list[dict]]:
    """Convenience wrapper: builds the graph, runs it to completion, returns
    (answer_text, citations) with duplicate citations collapsed."""
    app = build_graph(db, trace)
    messages = (history or []) + [{"role": "user", "content": user_message}]

    result = app.invoke({
        "repo_id": repo_id,
        "messages": messages,
        "citations": [],
        "steps_taken": 0,
        "final_answer": None,
    })

    seen, deduped = set(), []
    for c in result["citations"]:
        if c["chunk_id"] not in seen:
            seen.add(c["chunk_id"])
            deduped.append(c)

    return result["final_answer"], deduped
