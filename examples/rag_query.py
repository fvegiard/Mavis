#!/usr/bin/env python3
"""
example_rag.py — Example: query Mavis's RAG knowledge base.

This shows the basic pattern: embed a query, retrieve top-K, pass to Claude.
For the CLI equivalent, use `mavis-rag "your question"`.

Prerequisites:
  - export OPENROUTER_API_KEY=sk-or-v1-...
  - export ANTHROPIC_OAUTH_TOKEN=sk-ant-...
  - mavis-rag-eval passes 88% precision@1 (i.e., the cache is fresh)
"""
import sys
import os

# Add scripts/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import mavis_vectorize as mv
import subprocess


def query(question: str, top_k: int = 3, model: str = "claude-haiku-4-5") -> str:
    """Embed question, retrieve top-K chunks, ask Claude."""
    # 1. Retrieve top-K chunks via the vectorize script
    result = subprocess.run(
        ["python3", "/usr/local/bin/mavis-vectorize", "--query", question, "--top-k", str(top_k)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return f"[ERROR] retrieval failed: {result.stderr}"

    # 2. Parse the JSON output (after the stderr logs)
    import json
    output = result.stdout.strip()
    json_start = output.find("[")
    if json_start == -1:
        return "[ERROR] no chunks retrieved"
    chunks = json.loads(output[json_start:])

    # 3. Build context
    context = "\n\n".join([
        f"[Source {i+1}] (score={c.get('score', 0):.2f})\n{c.get('content', '')}"
        for i, c in enumerate(chunks[:top_k])
    ])

    # 4. Ask Claude
    prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {question}

Answer concisely in 1-2 sentences, citing source numbers."""

    result = subprocess.run(
        ["mavis-call", "--model", model, prompt, "500"],
        capture_output=True, text=True, timeout=60,
    )
    return result.stdout


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What is Mavis?"
    answer = query(question)
    print(f"Q: {question}")
    print(f"A: {answer}")
