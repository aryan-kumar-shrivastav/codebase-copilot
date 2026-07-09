"use client";

import { useEffect, useRef, useState } from "react";
import type { Repo } from "@/lib/api";
import MessageBubble, { UIMessage } from "./MessageBubble";

type Props = {
  repo: Repo | null;
  messages: UIMessage[];
  onSend: (text: string) => Promise<void>;
  sending: boolean;
};

export default function ChatWindow({ repo, messages, onSend, sending }: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || sending) return;
    const text = draft.trim();
    setDraft("");
    await onSend(text);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  const disabled = !repo || repo.status !== "ready";

  return (
    <div className="chat-panel">
      <div className="chat-scroll" ref={scrollRef}>
        {!repo && (
          <div className="empty-state">
            <div className="empty-state-title">Select or ingest a repo to get started</div>
            <div>Ask questions, generate docs, trace every retrieval step.</div>
          </div>
        )}
        {repo && repo.status !== "ready" && (
          <div className="empty-state">
            <div className="empty-state-title">
              {repo.status === "error" ? "Ingest failed" : "Indexing repository…"}
            </div>
            <div className="mono">
              {repo.status === "error" ? repo.error_message : "chunking + embedding in progress"}
            </div>
          </div>
        )}
        {repo && repo.status === "ready" && messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">{repo.name} is indexed and ready</div>
            <div>
              {repo.chunk_count} chunks across {repo.file_count} files. Ask anything.
            </div>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {sending && (
          <div className="message assistant">
            <div className="message-role">copilot</div>
            <div className="thinking-dots">retrieving · reasoning …</div>
          </div>
        )}
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <div className="chat-input-wrap">
          <textarea
            rows={1}
            placeholder={disabled ? "waiting for repo to be ready…" : "Ask about this codebase…"}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />
          <button className="send-btn" type="submit" disabled={disabled || sending || !draft.trim()}>
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
