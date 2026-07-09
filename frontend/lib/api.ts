const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Repo = {
  id: string;
  name: string;
  status: "pending" | "ingesting" | "ready" | "error";
  file_count: number;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
};

export type Citation = {
  chunk_id: string;
  file_path: string;
  symbol_name: string | null;
  start_line: number;
  end_line: number;
};

export type ChatResponse = {
  session_id: string;
  message_id: string;
  content: string;
  citations: Citation[];
  trace_id: string;
};

export type TraceEvent = {
  type: string;
  t: number;
  status?: string;
  duration_s?: number;
  [key: string]: unknown;
};

export type Trace = {
  trace_id: string;
  meta: Record<string, unknown>;
  events: TraceEvent[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listRepos: () => request<Repo[]>("/repos"),

  ingestRepo: (source_url: string, name?: string) =>
    request<Repo>("/repos", { method: "POST", body: JSON.stringify({ source_url, name }) }),

  getRepo: (repoId: string) => request<Repo>(`/repos/${repoId}`),

  sendMessage: (repo_id: string, message: string, session_id?: string | null) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ repo_id, message, session_id }),
    }),

  getTrace: (traceId: string) => request<Trace>(`/traces/${traceId}`),

  generateDoc: (repo_id: string, instruction: string) =>
    request<{ content: string; citations: Citation[]; trace_id: string }>("/actions", {
      method: "POST",
      body: JSON.stringify({ repo_id, action: "generate_doc", instruction }),
    }),
};
