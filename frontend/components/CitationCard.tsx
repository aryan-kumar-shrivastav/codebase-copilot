"use client";

import { useState } from "react";
import type { Citation } from "@/lib/api";

export default function CitationCard({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  const label = citation.symbol_name
    ? `${citation.file_path.split("/").pop()} · ${citation.symbol_name}`
    : `${citation.file_path.split("/").pop()}:${citation.start_line}`;

  return (
    <div style={{ display: "inline-flex", flexDirection: "column" }}>
      <button className="citation-pill" onClick={() => setOpen(!open)} type="button">
        <span>▸</span>
        {label}
        <span style={{ color: "var(--text-faint)" }}>
          L{citation.start_line}-{citation.end_line}
        </span>
      </button>
      {open && (
        <div className="citation-detail">
          {citation.file_path}:{citation.start_line}-{citation.end_line}
          <br />
          <span style={{ color: "var(--text-faint)" }}>
            (open this file in your editor at these lines — the chunk content itself
            isn't refetched here to keep the demo simple; wire this to a code-viewer
            endpoint for the full experience)
          </span>
        </div>
      )}
    </div>
  );
}
