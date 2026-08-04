#!/usr/bin/env python3
"""
ingest-docs.py — Auto-ingest documentation into mavis_knowledge.

Sources ingested (default):
- Anthropic API docs
- Claude Code repo
- GitHub Copilot docs
- Supabase docs

Usage:
  ingest-docs.py --source anthropic
  ingest-docs.py --source claude-code
  ingest-docs.py --source all
"""
import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
# Load mavis-vectorize dynamically (since it has a hyphen, not importable normally)
import importlib.util
_spec = importlib.util.spec_from_file_location("mavis_vectorize", SCRIPTS_DIR / "mavis-vectorize.py")
mv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mv)


SOURCES = {
    "claude-code": [
        "https://raw.githubusercontent.com/anthropics/claude-code/main/README.md",
        "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
    ],
    "anthropic-skills": [
        "https://raw.githubusercontent.com/anthropics/skills/main/skills/README.md",
    ],
    "mavis": [
        # Self-knowledge: Mavis's own README and INSTALL.md
        "file:///workspace/jarvis/README.md",
        "file:///workspace/jarvis/INSTALL.md",
        "file:///workspace/jarvis/CHANGELOG.md",
    ],
}


def fetch_url(url: str) -> str:
    """Fetch URL content (http/https/file). Returns plain text or empty on error."""
    try:
        if url.startswith("file://"):
            with open(url[7:]) as f:
                return f.read()[:50000]
        req = urllib.request.Request(url, headers={"User-Agent": "Mavis/5.0 (compatible; +https://MiniMax.local/mavis)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")[:50000]
    except Exception as e:
        print(f"  ✗ {url}: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 2000) -> list:
    """Simple chunking by paragraph + size."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) > chunk_size and current:
            chunks.append(current.strip())
            current = p
        else:
            current += "\n\n" + p
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if len(c) > 100]


def ingest_source(name: str, urls: list) -> int:
    """Ingest a source. Returns number of chunks embedded."""
    total = 0
    for url in urls:
        print(f"  → {url}")
        text = fetch_url(url)
        if not text:
            continue
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            # Use mavis-vectorize to embed (uses OpenRouter)
            try:
                # We need a way to embed and post to supabase
                # The mv.openai_embed returns a vector
                vec = mv.openai_embed(chunk)
                if not vec:
                    print(f"    chunk {i}: empty embedding (skipped)")
                    continue
                # Post to mavis_knowledge
                body = {
                    "topic": f"docs-{name}",
                    "type": "reference",
                    "tags": [name, "ingest", "auto"],
                    "content": chunk[:8000],  # Cap content size
                    "embedding": vec,  # Supabase auto-serializes
                    "confidence": 0.95,
                }
                result = mv.supa_post("mavis_knowledge", body)
                if result:
                    total += 1
                    if total % 5 == 0:
                        print(f"    {total} chunks ingested")
                else:
                    print(f"    chunk {i}: post returned empty")
            except Exception as e:
                print(f"    chunk {i} failed: {str(e)[:120]}")
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="all", choices=["all"] + list(SOURCES.keys()))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    sources = SOURCES if args.source == "all" else {args.source: SOURCES[args.source]}
    grand_total = 0
    for name, urls in sources.items():
        print(f"\n=== Ingesting {name} ({len(urls)} URLs) ===")
        if not args.dry_run:
            n = ingest_source(name, urls)
            grand_total += n
            print(f"  → {n} chunks ingested from {name}")
    print(f"\n✅ Total: {grand_total} chunks ingested")


if __name__ == "__main__":
    sys.exit(main())
