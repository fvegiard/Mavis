#!/usr/bin/env python3
"""
mavis-vectorize.py — Embed mavis_knowledge rows (or any text source) into pgvector-compatible 1536-dim vectors.

Reads from Supabase mavis_knowledge, finds rows where embedding is NULL or stale,
calls OpenAI text-embedding-3-small, and UPDATEs the embedding column.

Usage:
  mavis-vectorize                       # re-embed all NULL rows
  mavis-vectorize --rebuild             # wipe all embeddings and re-do everything
  mavis-vectorize --row-id 42           # one specific row
  mavis-vectorize --text "hello world"  # ad-hoc embed, prints vector
  mavis-vectorize --fetch-cache         # download all rows to local JSON cache (for client-side RAG)
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# --- Supabase config (read from env, fall back to hardcoded ref) ---
REF = os.environ.get("SUPABASE_REF", "hzdzeleznvxzncgzqiub")
SR_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6ZHplbGV6bnZ4em5jZ3pxaXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDE0NDY0MywiZXhwIjoyMDk5NzIwNjQzfQ.Vvs_oY4dY-vDGVyxEipltGA9s3XcqhQJV4XBpVOH-i4"
)
SUPABASE_URL = f"https://{REF}.supabase.co"

# --- Embedding config: OpenRouter (OpenAI keys in vault are invalid as of 2026-08-04) ---
# OpenRouter exposes OpenAI text-embedding-3-small at the same interface, so we
# hit https://openrouter.ai/api/v1/embeddings with Bearer OR_KEY.
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY_1") or os.environ.get("OPENAI_API_KEY_2") or os.environ.get("OPENAI_API_KEY_3") or os.environ.get("OPENAI_API_KEY")  # legacy fallback
EMBED_MODEL = "openai/text-embedding-3-small"  # 1536 dim via OpenRouter
EMBED_URL = "https://openrouter.ai/api/v1/embeddings" if OPENROUTER_KEY else "https://api.openai.com/v1/embeddings"
EMBED_AUTH = f"Bearer {OPENROUTER_KEY}" if OPENROUTER_KEY else f"Bearer {OPENAI_KEY}"


def supa_get(path: str, params: dict | None = None) -> list:
    """GET from Supabase REST. Returns parsed JSON list."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "apikey": SR_KEY,
        "Authorization": f"Bearer {SR_KEY}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def supa_patch(path: str, body: dict) -> dict:
    """PATCH Supabase REST. Returns parsed JSON."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "apikey": SR_KEY,
        "Authorization": f"Bearer {SR_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def supa_post(path: str, body: dict) -> dict:
    """POST (insert) to Supabase REST. Returns parsed JSON."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "apikey": SR_KEY,
        "Authorization": f"Bearer {SR_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def openai_embed(text: str) -> list:
    """Call embeddings API (OpenRouter preferred, OpenAI fallback). Returns 1536-dim float list."""
    if not (OPENROUTER_KEY or OPENAI_KEY):
        raise RuntimeError("No OPENROUTER_API_KEY or OPENAI_API_KEY in env")
    body = json.dumps({"input": text, "model": EMBED_MODEL}).encode("utf-8")
    req = urllib.request.Request(EMBED_URL, data=body, headers={
        "Authorization": EMBED_AUTH,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode("utf-8"))
        return resp["data"][0]["embedding"]


def embed_one_row(row: dict, verbose=True) -> bool:
    """Embed one mavis_knowledge row's content, PATCH it back."""
    text = row["content"]
    if not text or not text.strip():
        if verbose: print(f"  [{row['id']}] empty content, skip")
        return False
    if verbose: print(f"  [{row['id']}] topic={row.get('topic','?')} len={len(text)} chars -> embed", end="", flush=True)
    try:
        vec = openai_embed(text)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
        # Network/decoding errors only — generic Exception would hide real bugs
        if verbose: print(f" ERR: {e}")
        return False
    # PATCH embedding column. mavis_knowledge stores embedding as a stringified JSON
    # array of floats (Postgres text column). We re-stringify.
    supa_patch(f"mavis_knowledge?id=eq.{row['id']}", {"embedding": json.dumps(vec), "updated_at": "now()"})
    if verbose: print(f" ok ({len(vec)}d)")
    return True


def fetch_all_rows(force: bool = False) -> list:
    """Get all mavis_knowledge rows. If --rebuild, ignore existing embedding."""
    params = {"select": "id,topic,content,type,embedding,updated_at", "limit": 500}
    rows = supa_get("mavis_knowledge", params)
    if not force:
        rows = [r for r in rows if not r.get("embedding")]
    return rows


def cmd_vectorize(args):
    if args.text:
        print(f"# Using {EMBED_URL}", file=sys.stderr)
        vec = openai_embed(args.text)
        print(f"text: {args.text!r}")
        print(f"dim: {len(vec)}")
        print(f"first 5: {vec[:5]}")
        return
    if args.row_id:
        rows = supa_get("mavis_knowledge", {"select": "*", "id": f"eq.{args.row_id}"})
        if not rows:
            print(f"row {args.row_id} not found", file=sys.stderr)
            sys.exit(1)
        embed_one_row(rows[0])
        return
    if args.rebuild:
        # Wipe all embeddings first
        print("REBUILD: wiping all embeddings...")
        supa_patch("mavis_knowledge?id=gt.0", {"embedding": None})
    rows = fetch_all_rows(force=args.rebuild)
    if not rows:
        print("Nothing to embed.")
        return
    print(f"Embedding {len(rows)} rows...")
    ok, fail = 0, 0
    for r in rows:
        if embed_one_row(r):
            ok += 1
        else:
            fail += 1
    print(f"\nDone. ok={ok}, fail={fail}")


def cmd_fetch_cache(args):
    """Download all rows to local JSON for client-side RAG."""
    rows = supa_get("mavis_knowledge", {"select": "id,topic,content,type,tags,embedding", "limit": 500})
    cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "mavis_knowledge_cache.json")
    cache_path = os.path.abspath(cache_path)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(rows, f, indent=2)
    with_emb = sum(1 for r in rows if r.get("embedding"))
    print(f"  cached {len(rows)} rows ({with_emb} with embeddings) -> {cache_path}")
    print(f"  size: {os.path.getsize(cache_path) / 1024:.1f} KB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--text", help="Ad-hoc embed a single text, print vector")
    p.add_argument("--row-id", type=int, help="Embed one specific row id")
    p.add_argument("--rebuild", action="store_true", help="Wipe and re-embed everything")
    p.add_argument("--fetch-cache", action="store_true", help="Download all rows to local JSON")
    args = p.parse_args()
    if args.fetch_cache:
        cmd_fetch_cache(args)
    else:
        cmd_vectorize(args)


if __name__ == "__main__":
    main()
