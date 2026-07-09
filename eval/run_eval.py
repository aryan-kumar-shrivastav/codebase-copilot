"""
Small eval harness — the piece that separates a portfolio RAG demo from
one that shows you understand LLM evaluation. Run against a live backend
with a repo already ingested:

    python eval/run_eval.py --repo-id <id> --api-url http://localhost:8000

For each question in eval_set.jsonl, this checks:
  - retrieval_hit: did *any* returned citation come from an expected file
    (only scored for questions with `expected_files` set)
  - has_citations: did the agent cite anything at all (a zero-citation
    answer to a codebase question is a strong hallucination signal)
  - citation_count: how many distinct chunks backed the answer
  - latency_s: end-to-end request time

This is intentionally simple (no LLM-graded faithfulness scoring, which
needs its own careful prompt + costs API calls) — a good next step once
the base pipeline is solid, noted in the README.
"""
from __future__ import annotations

import argparse
import json
import time

import httpx


def load_eval_set(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def run(api_url: str, repo_id: str, eval_path: str) -> None:
    cases = load_eval_set(eval_path)
    results = []
    session_id = None

    for case in cases:
        start = time.time()
        resp = httpx.post(
            f"{api_url}/chat",
            json={"repo_id": repo_id, "session_id": session_id, "message": case["question"]},
            timeout=60,
        )
        latency = time.time() - start
        resp.raise_for_status()
        data = resp.json()
        session_id = None  # fresh session per question so answers don't leak context between cases

        citations = data["citations"]
        cited_files = {c["file_path"] for c in citations}

        retrieval_hit = None
        if "expected_files" in case:
            retrieval_hit = any(
                any(ef in cf for ef in case["expected_files"]) for cf in cited_files
            )

        results.append({
            "question": case["question"],
            "type": case.get("type"),
            "has_citations": len(citations) > 0,
            "citation_count": len(citations),
            "retrieval_hit": retrieval_hit,
            "latency_s": round(latency, 2),
        })

    _print_report(results)


def _print_report(results: list[dict]) -> None:
    n = len(results)
    with_citations = sum(r["has_citations"] for r in results)
    scored_hits = [r for r in results if r["retrieval_hit"] is not None]
    hit_rate = (sum(r["retrieval_hit"] for r in scored_hits) / len(scored_hits)) if scored_hits else None
    avg_latency = sum(r["latency_s"] for r in results) / n if n else 0

    print(f"\n{'question':<55} {'cites':>6} {'hit':>5} {'latency':>8}")
    print("-" * 78)
    for r in results:
        hit_str = "-" if r["retrieval_hit"] is None else ("Y" if r["retrieval_hit"] else "N")
        print(f"{r['question'][:53]:<55} {r['citation_count']:>6} {hit_str:>5} {r['latency_s']:>7}s")

    print("-" * 78)
    print(f"Answers with >=1 citation: {with_citations}/{n}")
    if hit_rate is not None:
        print(f"Retrieval recall@expected_files: {hit_rate:.0%} ({len(scored_hits)} scored questions)")
    print(f"Avg latency: {avg_latency:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--eval-path", default="eval/eval_set.jsonl")
    args = parser.parse_args()
    run(args.api_url, args.repo_id, args.eval_path)
