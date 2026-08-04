#!/usr/bin/env python3
"""
mavis-rag-eval.py — Evaluate mavis-rag retrieval quality against golden queries.

Tests: 5 hand-crafted queries with expected top-1 topic. Reports precision@1, recall, MRR.

Usage:
  mavis-rag-eval             # run the full eval
  mavis-rag-eval --query "Mavis arch|arch|routing"   # one custom query
  mavis-rag-eval --verbose   # print full retrieved chunks per query
"""
import argparse
import importlib.util
import os
import sys

# Load mavis-vectorize + mavis-rag helpers
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("mavis_rag", os.path.join(SCRIPT_DIR, "mavis-rag.py"))
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv if False else mr)  # noqa: F821

# Golden queries: (query, expected_top_topic, expected_keywords_in_answer)
GOLDEN_QUERIES = [
    {
        "query": "Mavis hosting agent architecture",
        "expected_topic": "routing",
        "expected_keywords": ["supervisor", "cascade", "circuit"],
        "why": "Mavis's role is documented in the 'routing' topic",
    },
    {
        "query": "Kimi K3 pricing per million tokens",
        "expected_topic": "kimi",
        "expected_keywords": ["$3", "$15", "MoE"],
        "why": "Kimi pricing is in the 'kimi' topic",
    },
    {
        "query": "Codex 429 rate limit error",
        "expected_topic": "codex-429-handling",
        "expected_keywords": ["retry", "backoff", "usage"],
        "why": "Codex 429 handling is its own topic",
    },
    {
        "query": "Tailscale debug status check",
        "expected_topic": "tailscale",
        "expected_keywords": ["status", "json", "service"],
        "why": "Tailscale debug is in 'tailscale' topic",
    },
    {
        "query": "Cron schedule for Tailscale bootstrap home",
        "expected_topic": "cron-bootstrap-tailscale-maison",  # or 'cron' or 'tailscale'
        "expected_keywords": ["*/15", "winget", "auto"],
        "why": "Cron + tailscale should match the migrated cron row",
    },
    {
        "query": "Python 3.11 3.14 uv install version",
        "expected_topic": "state",
        "expected_keywords": ["uv", "python"],
        "why": "Python version state snapshot should match",
    },
    {
        "query": "OpenAI API key 401 invalid",
        "expected_topic": "openai-529-overloaded",  # or any openai-* topic
        "expected_keywords": ["401", "invalid", "key"],
        "why": "OpenAI errors are in openai-* topics",
    },
    {
        "query": "Git auto commit setup Mavis",
        "expected_topic": "git",
        "expected_keywords": ["commit", "auto"],
        "why": "Git setup is in 'git' topic",
    },
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--query", help="One custom query in 'query|expected_topic|kw1,kw2' format")
    p.add_argument("--verbose", action="store_true", help="Print full retrieved chunks per query")
    p.add_argument("--no-call", action="store_true", help="Skip Claude call, only test retrieval")
    args = p.parse_args()

    if args.query:
        parts = args.query.split("|")
        queries = [{
            "query": parts[0],
            "expected_topic": parts[1] if len(parts) > 1 else None,
            "expected_keywords": parts[2].split(",") if len(parts) > 2 else [],
            "why": "custom",
        }]
    else:
        queries = GOLDEN_QUERIES

    print(f"# mavis-rag-eval — {len(queries)} golden queries")
    print(f"# mode: {'retrieval-only' if args.no_call else 'retrieval + LLM'}")
    print()

    results = []
    for i, q in enumerate(queries, 1):
        print(f"## Query {i}: {q['query']!r}")
        print(f"   expected topic: {q['expected_topic']!r}")
        try:
            chunks = mr.retrieve(q["query"], top_k=5)
        except (TimeoutError, OSError, ValueError, KeyError) as e:
            print(f"   ERROR retrieving: {e}")
            results.append({"query": q["query"], "error": str(e)})
            continue

        # Score retrieval
        top_topic = chunks[0]["topic"] if chunks else None
        top_score = chunks[0]["score"] if chunks else 0
        expected_in_top5 = any(c["topic"] == q["expected_topic"] for c in chunks)
        in_top1 = top_topic == q["expected_topic"]

        if args.verbose:
            print("   top 5:")
            for c in chunks:
                marker = "✓" if c["topic"] == q["expected_topic"] else " "
                print(f"     {marker} [{c['id']}] {c['topic']} (score={c['score']:.3f})")

        # Score answer (if --no-call, skip)
        answer_has_kw = True
        if not args.no_call and chunks:
            context = mr.build_context(chunks)
            try:
                from mavis_call import call_mavis_inline  # type: ignore
                answer = call_mavis_inline(context, q["query"])
            except (ImportError, ModuleNotFoundError, AttributeError, TimeoutError, OSError):
                # Fallback: just count keywords in the retrieved content
                answer = "\n".join(c["content"] for c in chunks)
                print("   (no LLM call, scoring against retrieved content only)")
            answer_has_kw = all(kw.lower() in answer.lower() for kw in q["expected_keywords"])
            if args.verbose:
                print(f"   answer keywords found: {answer_has_kw}")

        results.append({
            "query": q["query"],
            "top_topic": top_topic,
            "top_score": top_score,
            "expected_topic": q["expected_topic"],
            "in_top1": in_top1,
            "in_top5": expected_in_top5,
            "answer_has_kw": answer_has_kw,
        })

        marker = "✓✓" if in_top1 else ("✓" if expected_in_top5 else "✗")
        print(f"   {marker} top1={top_topic} (score={top_score:.3f}) — expected={q['expected_topic']}")
        if not args.no_call:
            print(f"   keywords_in_answer={answer_has_kw}")
        print()

    # Summary
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    n = len(results)
    n_top1 = sum(1 for r in results if r.get("in_top1"))
    n_top5 = sum(1 for r in results if r.get("in_top5"))
    n_kw = sum(1 for r in results if r.get("answer_has_kw"))
    n_err = sum(1 for r in results if "error" in r)
    print(f"  Queries: {n}")
    print(f"  Precision@1: {n_top1}/{n} = {n_top1/n*100:.0f}%")
    print(f"  Recall@5:    {n_top5}/{n} = {n_top5/n*100:.0f}%")
    if not args.no_call:
        print(f"  Keyword hit: {n_kw}/{n} = {n_kw/n*100:.0f}%")
    print(f"  Errors:      {n_err}/{n}")

    # MRR
    reciprocal_ranks = []
    for r in results:
        if r.get("in_top1"):
            reciprocal_ranks.append(1.0)
        elif r.get("in_top5"):
            reciprocal_ranks.append(0.5)  # not exact rank, just an estimate
        else:
            reciprocal_ranks.append(0.0)
    if reciprocal_ranks:
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        print(f"  MRR (approx): {mrr:.3f}")

    return 0 if n_err == 0 and n_top1 >= n // 2 else 1


if __name__ == "__main__":
    sys.exit(main())
