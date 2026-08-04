#!/usr/bin/env python3
"""
mavis-rag.py — RAG-enhanced Mavis call.

1. Embed the user query via OpenRouter (text-embedding-3-small, 1536 dim)
2. Cosine-similarity against cached mavis_knowledge embeddings (client-side, no RPC needed)
3. Build a system prompt with the top-K chunks as context
4. Call mavis-call wrapper (which calls Claude with the rate-limit-pool-unlock trick)

Usage:
  mavis-rag "comment installer Claude Code sur MX Linux"
  mavis-rag --top-k 3 --threshold 0.2 "Tailscale debug"
  mavis-rag --refresh-cache            # re-download mavis_knowledge
  mavis-rag --no-context "..."         # skip RAG, just call Mavis
  mavis-rag --show-sources "..."       # print retrieved chunks before answer
"""
import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys

# Import the embedding helper from mavis-vectorize.py
# Use realpath to resolve symlinks (so /usr/local/bin/mavis-rag -> /workspace/jarvis/scripts/mavis-rag.py)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("mavis_vectorize", os.path.join(SCRIPT_DIR, "mavis-vectorize.py"))
mv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv)


# --- Cache management ---
CACHE_PATH = os.path.join(SCRIPT_DIR, "..", "data", "mavis_knowledge_cache.json")
CACHE_PATH = os.path.abspath(CACHE_PATH)


def refresh_cache() -> list:
    """Re-download mavis_knowledge rows from Supabase."""
    print("# Refreshing cache from Supabase...", file=sys.stderr)
    rows = mv.supa_get("mavis_knowledge", {"select": "id,topic,content,type,tags,embedding", "limit": 500})
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(rows, f)
    return rows


def load_cache() -> list:
    """Load cache from disk, refresh if missing."""
    if not os.path.exists(CACHE_PATH):
        return refresh_cache()
    with open(CACHE_PATH) as f:
        return json.load(f)


def cosine(a: list, b: list) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def parse_embedding(emb) -> list:
    """mavis_knowledge stores embedding as a JSON string. Parse it back to list[float]."""
    if isinstance(emb, list):
        return emb
    if isinstance(emb, str):
        return json.loads(emb)
    return []


def retrieve(query: str, top_k: int = 5) -> list:
    """Embed query, score all cache rows, return top_k with scores."""
    rows = load_cache()
    qvec = mv.openai_embed(query)
    scored = []
    for r in rows:
        emb = parse_embedding(r.get("embedding") or [])
        if not emb:
            continue
        score = cosine(qvec, emb)
        scored.append({**r, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def build_context(chunks: list, max_chars: int = 3000) -> str:
    """Format top-K chunks as a system context block."""
    if not chunks:
        return ""
    lines = ["# Contexte pertinent (RAG depuis Supabase mavis_knowledge)\n"]
    char_count = 0
    for i, c in enumerate(chunks, 1):
        block = f"## [{i}] {c.get('topic', '?')} ({c.get('type', '?')}, score={c.get('score', 0):.3f})\n{c.get('content', '')}\n"
        if char_count + len(block) > max_chars:
            break
        lines.append(block)
        char_count += len(block)
    return "\n".join(lines)


def call_mavis(system: str, prompt: str, model: str = "claude-haiku-4-5", tokens: int = 1024) -> int:
    """Delegate to mavis-call wrapper (assumes /usr/local/bin/mavis-call exists or is at /workspace/jarvis/scripts/mavis-call).

    Default = Haiku 4.5 because:
    - Sonnet 5/4-6 429 on long system prompts (rate-limit-pool unlock has tighter cap on premium models)
    - Haiku is on a separate (cheap) tier so it stays available
    - 1M context window, fast, fine for RAG-grounded answers
    """
    jarvis_home = os.environ.get("JARVIS_HOME", "/workspace/jarvis")
    wrapper = os.path.join(jarvis_home, "scripts", "mavis-call")
    if not os.path.exists(wrapper):
        # Try the system-installed symlink
        wrapper = "/usr/local/bin/mavis-call"
    if not os.path.exists(wrapper):
        # Last resort: print prompt + context to stdout (so user can pipe it somewhere)
        print("=== mavis-call wrapper not found. Context + prompt: ===", file=sys.stderr)
        print(system[:500] if system else "(no system)", file=sys.stderr)
        print("---", file=sys.stderr)
        print(prompt)
        return 0
    cmd = [wrapper, "--model", model, prompt, str(tokens)]
    if system:
        cmd.insert(3, "--system")
        cmd.insert(4, system)
    return subprocess.call(cmd)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("prompt", help="Question to ask Mavis")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--threshold", type=float, default=0.25, help="Min similarity score to include")
    p.add_argument("--model", default="claude-haiku-4-5", help="Model for final answer (default: haiku-4-5, separate cheap tier)")
    p.add_argument("--tokens", type=int, default=1024)
    p.add_argument("--no-context", action="store_true", help="Skip RAG, just call Mavis directly")
    p.add_argument("--refresh-cache", action="store_true", help="Re-download mavis_knowledge before retrieving")
    p.add_argument("--show-sources", action="store_true", help="Print retrieved chunks before answer")
    args = p.parse_args()

    if args.no_context:
        return call_mavis("", args.prompt, args.model, args.tokens)

    if args.refresh_cache:
        refresh_cache()

    # 1. Retrieve
    chunks = retrieve(args.prompt, args.top_k)
    chunks = [c for c in chunks if c.get("score", 0) >= args.threshold]

    print(f"\n# RAG: {len(chunks)} chunks above threshold {args.threshold}", file=sys.stderr)
    if args.show_sources:
        for c in chunks:
            print(f"  - [{c['id']}] {c['topic']} (score={c['score']:.3f}): {c['content'][:80]}...", file=sys.stderr)

    # 2. Build context
    context = build_context(chunks)
    if not context:
        print("# RAG: no context found above threshold, falling back to direct call\n", file=sys.stderr)
        return call_mavis("", args.prompt, args.model, args.tokens)

    # 3. Call Mavis with context
    system_prompt_path = os.path.expanduser("~/.claude/jarvis/SYSTEM_PROMPT.md")
    base_system = ""
    if os.path.exists(system_prompt_path):
        with open(system_prompt_path) as f:
            base_system = f.read()

    full_system = (base_system + "\n\n" + context) if base_system else context

    return call_mavis(full_system, args.prompt, args.model, args.tokens)


if __name__ == "__main__":
    sys.exit(main())
