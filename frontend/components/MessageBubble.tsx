"use client";

import type { Citation } from "@/lib/api";
import CitationCard from "./CitationCard";

export type UIMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

export default function MessageBubble({ message }: { message: UIMessage }) {
  return (
    <div className={`message ${message.role}`}>
      <div className="message-role">{message.role === "user" ? "you" : "copilot"}</div>
      <div className="message-content">{message.content}</div>
      {message.citations && message.citations.length > 0 && (
        <div className="citations-row">
          {message.citations.map((c) => (
            <CitationCard key={c.chunk_id} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}
