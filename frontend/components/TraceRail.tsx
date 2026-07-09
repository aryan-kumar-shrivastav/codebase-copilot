"use client";

import type { Trace } from "@/lib/api";

function summarize(event: Trace["events"][number]): string {
  if (event.type === "tool_call") {
    const args = event.args ? JSON.stringify(event.args) : "";
    return `${event.tool}(${args})`.slice(0, 160);
  }
  if (event.type === "llm_call") {
    return `model reasoning step ${event.step_number ?? ""}`.trim();
  }
  if (event.error) {
    return String(event.error);
  }
  return Object.entries(event)
    .filter(([k]) => !["type", "t", "status", "duration_s"].includes(k))
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(" ")
    .slice(0, 160);
}

export default function TraceRail({ trace }: { trace: Trace | null }) {
  return (
    <div className="panel trace-rail">
      <div className="panel-header">
        <span className="panel-title">Trace</span>
        {trace && <span className="mono" style={{ fontSize: 10, color: "var(--text-faint)" }}>{trace.trace_id.slice(0, 8)}</span>}
      </div>
      <div className="trace-scroll">
        {!trace && (
          <div className="trace-empty">
            Every agent turn logs its retrieval calls, tool calls, and reasoning
            steps here — this is what makes the answer auditable instead of a
            black box. Send a message to see it populate.
          </div>
        )}
        {trace?.events.map((event, i) => (
          <div key={i} className={`trace-event ${event.type} ${event.status === "error" ? "error" : ""}`}>
            <div className="trace-event-head">
              <span>{event.type}</span>
              <span className="trace-event-time">
                t+{event.t}s{event.duration_s !== undefined ? ` (${event.duration_s}s)` : ""}
              </span>
            </div>
            <div className="trace-event-body">{summarize(event)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
