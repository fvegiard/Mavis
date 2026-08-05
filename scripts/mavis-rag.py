#!/usr/bin/env python3
"""
mavis-rag — Semantic search over mavis_knowledge (Supabase) + Claude answer.

Flow:
  1. Embed query via OpenRouter text-embedding-3-small (1536 dim)
  2. Retrieve top-K from mavis_knowledge via REST (compute cosine in Python)
  3. Inject context into Claude API call (mavis-call style)

Usage:
  mavis-rag "what is tailscale debug flow"
  mavis-rag "jarvis install" --top-k 5
  mavis-rag "x" --no-llm   # just show the retrieved chunks
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from urllib import request, error

SUPABASE_URL = "https://hzdzeleznvxzncgzqiub.supabase.co"
SUPABASE_KEY_FILE = Path("/root/.jarvis-secrets/supabase_service_role")
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIM = 1536


def _load_key():
    if not SUPABASE_KEY_FILE.exists():
        raise SystemExit(f"Missing {SUPABASE_KEY_FILE}. Save service_role key there.")
    return SUPABASE_KEY_FILE.read_text().strip()


def _embed(text: str) -> list[float]:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("No OPENROUTER_API_KEY in env")
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mavis/5.0",
        "HTTP-Referer": "https://mavis.local",
    }
    body = {"model": EMBEDDING_MODEL, "input": text[:8000]}
    data = json.dumps(body).encode()
    req = request.Request(url=url, data=data, method="POST", headers=headers)
    with request.urlopen(req, timeout=60) as resp:
        obj = json.loads(resp.read().decode())
    return obj["data"][0]["embedding"]


def _fetch_all_chunks(svc_key: str) -> list[dict]:
    """Pull all rows from mavis_knowledge (vectors + content + topic)."""
    url = f"{SUPABASE_URL}/rest/v1/mavis_knowledge?select=id,topic,type,content,source,tags,embedding&limit=500"
    headers = {
        "apikey": svc_key,
        "Authorization": f"Bearer {svc_key}",
    }
    req = request.Request(url=url, headers=headers)
    with request.urlopen(req, timeout=60) as resp:
        rows = json.loads(resp.read().decode())
    return rows


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _search(query_vec, chunks, top_k):
    scored = []
    for c in chunks:
        emb = c.get("embedding")
        if not emb:
            continue
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                continue
        if not isinstance(emb, list):
            continue
        score = _cosine(query_vec, emb)
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def _format_context(chunks_with_scores):
    out = []
    for score, c in chunks_with_scores:
        title = (c.get("content","")[:80] + "...") if c.get("content") else ""
        body = c.get("content", "")
        if not body:
            continue
        out.append(f"### [{c.get('topic','')}/{c.get('type','')}] {title}  (sim={score:.3f})\n{body[:1500]}")
    return "\n\n".join(out)


def _call_claude(prompt: str, context: str) -> dict:
    """Call Claude via OpenRouter (works in this sandbox)."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("No OPENROUTER_API_KEY in env")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mavis/5.0",
    }
    full_prompt = (
        "You are Mavis, Francis Végiard's personal AI orchestrator. "
        "Answer the user's question using ONLY the context provided below. "
        "Cite sources by [topic/type] at the end of each claim. "
        "If the context doesn't contain the answer, say so clearly.\n\n"
        f"=== CONTEXT ===\n{context}\n\n=== QUESTION ===\n{prompt}\n\n=== ANSWER ==="
    )
    body = {
        "model": "anthropic/claude-sonnet-4.5",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.3,
    }
    data = json.dumps(body).encode()
    req = request.Request(url=url, data=data, method="POST", headers=headers)
    t0 = time.time()
    with request.urlopen(req, timeout=120) as resp:
        obj = json.loads(resp.read().decode())
    text = obj.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {
        "text": text,
        "model": obj.get("model", ""),
        "input_tokens": obj.get("usage", {}).get("prompt_tokens", 0),
        "output_tokens": obj.get("usage", {}).get("completion_tokens", 0),
        "latency": time.time() - t0,
    }


def main():
    p = argparse.ArgumentParser(prog="mavis-rag", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="?", help="search query (or stdin)")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--no-llm", action="store_true", help="just show retrieved chunks, skip Claude")
    p.add_argument("--json", action="store_true", help="raw JSON output")
    p.add_argument("--min-score", type=float, default=0.0, help="filter chunks below this cosine score")
    args = p.parse_args()

    query = args.query
    if not query and not sys.stdin.isatty():
        query = sys.stdin.read().strip()
    if not query:
        p.error("query required (or pipe via stdin)")

    svc = _load_key()
    t0 = time.time()
    print(f"[embed query via {EMBEDDING_MODEL}...]", file=sys.stderr)
    qvec = _embed(query)
    print(f"[fetch {EMBEDDING_DIM}-dim corpus...]", file=sys.stderr)
    chunks = _fetch_all_chunks(svc)
    print(f"[scoring {len(chunks)} chunks...]", file=sys.stderr)
    top = _search(qvec, chunks, args.top_k)
    top = [(s, c) for s, c in top if s >= args.min_score]

    if args.no_llm:
        if args.json:
            print(json.dumps([{"score": s, **c} for s, c in top], indent=2, default=str))
        else:
            for s, c in top:
                print(f"\n--- score={s:.3f} id={c.get('id')} [{c.get('topic')}/{c.get('type')}] ---")
                print((c.get("content") or "")[:600])
        print(f"\n[retrieval-only, {time.time()-t0:.1f}s]", file=sys.stderr)
        return

    context = _format_context(top)
    if not context:
        print(f"No relevant context found for: {query!r}")
        return
    result = _call_claude(query, context)
    print(result["text"])
    print(
        f"\n[rag: top{args.top_k} ctx={len(context)}c "
        f"claude={result['model']} in={result['input_tokens']} out={result['output_tokens']} "
        f"{result['latency']:.1f}s total={time.time()-t0:.1f}s]",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
