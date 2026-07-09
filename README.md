# Codebase Copilot

A "Research & Ops Copilot" scoped to one domain: source code. Point it at
a git repo, ask questions with cited answers, generate docs, and (once
you wire in the stubbed action) open PRs — all with retrieval, memory,
and observability you can actually inspect.

This is a portfolio/learning build. It's structured to be genuinely run
locally with `docker-compose up`, not just read as pseudocode — the
chunker and API layer are tested and verified in this repo (see
"What's actually been tested" below).

## Why codebases, and why this architecture

Generic RAG (chunk by token count, embed, cosine-search) works poorly on
code: fixed-size windows cut functions in half, and a lot of the most
useful questions ("who calls this?") have an exact right answer that
embeddings are the wrong tool for. This project's answers to that:

- **AST-aware chunking** (tree-sitter): chunk by function/class/method,
  not token windows. See `backend/app/ingest/chunker.py`.
- **Hybrid retrieval**: vector search for conceptual questions, exact
  symbol/grep search for "who calls X" questions — the agent picks per
  question. See `backend/app/retrieval/` and `backend/app/agent/tools.py`.
- **A visible reasoning trail**: every tool call, retrieval, and LLM step
  is logged to a per-turn trace and rendered in the frontend's trace rail,
  so an answer is auditable, not a black box. See
  `backend/app/observability/tracing.py`.
- **An eval harness**: retrieval recall and citation-grounding checks
  against a small question set, not just vibes. See `eval/run_eval.py`.

## Architecture

```
frontend (Next.js)  →  backend (FastAPI)  →  Postgres + pgvector
                              │
                        agent/graph.py (LangGraph state machine)
                              │
                golden path: retrieve / find_symbol / find_callers / grep
```

- `backend/app/ingest/` — clone repo → walk files → AST-chunk → embed → store
- `backend/app/retrieval/` — vector search, exact symbol/grep search, re-ranking
- `backend/app/agent/` — LangGraph tool-calling loop + doc-generation action
- `backend/app/observability/` — per-turn trace logging
- `backend/app/api/` — FastAPI routes (`/repos`, `/chat`, `/actions`, `/traces`)
- `frontend/` — Next.js chat UI with an inline trace panel
- `eval/` — sample question set + a runner that scores retrieval recall and citation coverage

## Running it

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY and OPENAI_API_KEY (or VOYAGE_API_KEY) in .env

docker-compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:3000

Then, from the UI: paste a public git URL to ingest a repo, wait for its
status to flip to `ready`, and start asking questions.

To run the eval harness once a repo is ingested:

```bash
python eval/run_eval.py --repo-id <repo-id-from-the-UI-or-/repos-endpoint>
```

## What's actually been tested (and what isn't)

Built and iterated in a sandboxed dev environment without a live
Postgres/Docker available, so here's the honest state:

- ✅ **Chunker**: unit-tested (`backend/tests/test_chunker.py`, 6 passing
  tests) against a real tree-sitter parse — verified it correctly splits
  a class into class + method-level chunks with accurate line ranges,
  and falls back cleanly for unrecognized file types.
- ✅ **Backend imports & routing**: the FastAPI app imports cleanly and
  all routes (`/repos`, `/chat`, `/actions`, `/traces`) are registered
  correctly — verified via the OpenAPI schema.
- ✅ **Frontend**: `next build` compiles and type-checks with zero errors.
- ⚠️ **Not runnable end-to-end here**: no Postgres/pgvector or Docker in
  this environment, so the full ingest → embed → retrieve → agent loop
  hasn't been exercised against a live database or a real Anthropic/OpenAI
  API key. The code is written and structured carefully, but **run it
  yourself via `docker-compose up` and expect to debug the first real
  end-to-end pass** — that's normal for a project this size, not a sign
  something here is decorative.

## Known gaps / good next steps for a portfolio writeup

- **Re-ranking** currently uses a cheap lexical-overlap heuristic
  (`backend/app/retrieval/rerank.py`) instead of a real cross-encoder.
  Swapping in `cross-encoder/ms-marco-MiniLM-L-6-v2` (via
  sentence-transformers) or Voyage's rerank endpoint and measuring the
  recall delta is a strong before/after chart for a writeup.
- **`propose_fix` is a stub** (`backend/app/agent/tools.py`). Wiring it
  up for real needs: a git worktree per request, a sandboxed test runner
  (container per attempt), and the GitHub API for opening a draft PR —
  deliberately scoped out here since it's the highest-stakes, most
  infra-heavy piece and shouldn't be rushed.
- **Project memory** (`ChatSession.memory` in `models.py`) is a schema
  field with nothing writing to it yet — a good place to add "the agent
  learned this team avoids pattern X" style durable facts.
- **Eval harness** only checks retrieval recall and citation presence,
  not answer faithfulness. Adding an LLM-graded faithfulness check
  (a second model scoring "is this claim supported by the cited chunk")
  is the natural next step, and worth clearly labeling as more expensive
  per-run.
- **Embedding provider A/B test**: the `embedder.py` abstraction supports
  swapping OpenAI's `text-embedding-3-small` for Voyage's `voyage-code-2`
  with a one-line config change — running both against the eval set and
  comparing recall is a concrete, citable result for a portfolio.

## Extending: PR actions

Before enabling `propose_fix` for real:
1. Clone into a scratch git worktree per request (not the shared ingest clone)
2. Ask the LLM for a diff scoped to the relevant file(s)
3. Apply it, run the project's actual test suite inside a container
4. Only push a branch + open a draft PR (via `PyGithub` or the raw GitHub
   API) if tests pass — never push an unverified diff
