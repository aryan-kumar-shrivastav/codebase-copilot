"""
Minimal observability layer: every agent run gets a trace_id, and every
step (retrieval call, tool call, LLM call) appends a structured event to
that trace. Traces are written as JSON files for the MVP — swap for
LangSmith, or a `traces` table, once you want a real dashboard/search UI.

The point isn't the storage format, it's the discipline of logging enough
at each step to answer "why did the agent answer this way" after the
fact: what was retrieved, what tools ran, what the LLM saw.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager

from app.config import settings


class Trace:
    def __init__(self, trace_id: str | None = None, meta: dict | None = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.events: list[dict] = []
        self.meta = meta or {}
        self.started_at = time.time()

    def log(self, event_type: str, **payload) -> None:
        self.events.append({
            "type": event_type,
            "t": round(time.time() - self.started_at, 4),
            **payload,
        })

    @contextmanager
    def step(self, event_type: str, **payload):
        """Times a block and logs its duration alongside the given payload,
        e.g. `with trace.step("vector_search", query=q): ...`"""
        start = time.time()
        try:
            yield self
            self.log(event_type, duration_s=round(time.time() - start, 4), **payload, status="ok")
        except Exception as exc:  # noqa: BLE001 - re-raised after logging
            self.log(event_type, duration_s=round(time.time() - start, 4), **payload,
                      status="error", error=str(exc))
            raise

    def save(self) -> str:
        os.makedirs(settings.trace_log_path, exist_ok=True)
        path = os.path.join(settings.trace_log_path, f"{self.trace_id}.json")
        with open(path, "w") as f:
            json.dump({"trace_id": self.trace_id, "meta": self.meta, "events": self.events}, f, indent=2)
        return path


def load_trace(trace_id: str) -> dict | None:
    path = os.path.join(settings.trace_log_path, f"{trace_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)
