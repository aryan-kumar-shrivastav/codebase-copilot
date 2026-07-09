"use client";

import { useState } from "react";
import type { Repo } from "@/lib/api";

type Props = {
  repos: Repo[];
  selectedRepoId: string | null;
  onSelect: (repoId: string) => void;
  onIngest: (sourceUrl: string, name?: string) => Promise<void>;
};

export default function RepoSelector({ repos, selectedRepoId, onSelect, onIngest }: Props) {
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    try {
      await onIngest(url.trim());
      setUrl("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel">
      <div className="brand">
        <div className="brand-mark" />
        <div>
          <div className="brand-name">Codebase Copilot</div>
          <div className="brand-sub">retrieval + agent · v0.1</div>
        </div>
      </div>

      <div className="panel-header">
        <span className="panel-title">Repositories</span>
      </div>

      <div className="repo-list">
        {repos.length === 0 && (
          <div style={{ padding: 12, color: "var(--text-faint)", fontSize: 12 }}>
            No repos indexed yet — paste a git URL below to ingest one.
          </div>
        )}
        {repos.map((repo) => (
          <div
            key={repo.id}
            className={`repo-item ${repo.id === selectedRepoId ? "active" : ""}`}
            onClick={() => onSelect(repo.id)}
          >
            <div className="repo-name">{repo.name}</div>
            <div className="repo-meta">
              <span className={`status-dot ${repo.status}`} />
              <span>{repo.status}</span>
              {repo.status === "ready" && <span>· {repo.chunk_count} chunks</span>}
            </div>
          </div>
        ))}
      </div>

      <form className="ingest-form" onSubmit={handleSubmit}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/org/repo"
        />
        <button className="btn" type="submit" disabled={submitting || !url.trim()}>
          {submitting ? "Ingesting…" : "Ingest repo"}
        </button>
      </form>
    </div>
  );
}
