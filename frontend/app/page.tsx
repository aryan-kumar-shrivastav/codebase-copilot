"use client";

import { useEffect, useState, useCallback } from "react";
import { api, Repo, Trace } from "@/lib/api";
import RepoSelector from "@/components/RepoSelector";
import ChatWindow from "@/components/ChatWindow";
import TraceRail from "@/components/TraceRail";
import type { UIMessage } from "@/components/MessageBubble";

export default function Page() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [sending, setSending] = useState(false);

  const refreshRepos = useCallback(async () => {
    try {
      const list = await api.listRepos();
      setRepos(list);
    } catch {
      // backend not reachable yet — surfaced via empty state, no need to throw
    }
  }, []);

  useEffect(() => {
    refreshRepos();
    const interval = setInterval(refreshRepos, 4000); // poll for ingest status
    return () => clearInterval(interval);
  }, [refreshRepos]);

  const selectedRepo = repos.find((r) => r.id === selectedRepoId) || null;

  async function handleIngest(sourceUrl: string, name?: string) {
    const repo = await api.ingestRepo(sourceUrl, name);
    setRepos((prev) => [repo, ...prev]);
    setSelectedRepoId(repo.id);
    setMessages([]);
    setSessionId(null);
    setTrace(null);
  }

  function handleSelect(repoId: string) {
    setSelectedRepoId(repoId);
    setMessages([]);
    setSessionId(null);
    setTrace(null);
  }

  async function handleSend(text: string) {
    if (!selectedRepo) return;
    const userMsg: UIMessage = { id: `local-${Date.now()}`, role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    try {
      const res = await api.sendMessage(selectedRepo.id, text, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        { id: res.message_id, role: "assistant", content: res.content, citations: res.citations },
      ]);
      const fullTrace = await api.getTrace(res.trace_id).catch(() => null);
      setTrace(fullTrace);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: `Something went wrong talking to the backend: ${(err as Error).message}`,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="app-shell">
      <RepoSelector
        repos={repos}
        selectedRepoId={selectedRepoId}
        onSelect={handleSelect}
        onIngest={handleIngest}
      />
      <ChatWindow repo={selectedRepo} messages={messages} onSend={handleSend} sending={sending} />
      <TraceRail trace={trace} />
    </div>
  );
}
