#!/usr/bin/env python3
"""
example_multi_provider.py — Example: route a query through the best available LLM.

This shows how to use mavis-providers to auto-route to the cheapest
available model (or force a specific provider/model).

The optimal chain as of 2026-08-04:
  1. openrouter-free (FREE, e.g. Nemotron 3 Ultra 1M context)
  2. claude-oauth (Fable 5, premium direct)
  3. copilot (RESERVED for commit/review)
  4. groq (fastest, 230ms)
  5. openrouter (variety backup)
"""
import sys
import os
import subprocess


def call(prompt: str, provider: str = None, model: str = None) -> str:
    """Call via mavis-providers. If provider/model not given, auto-route."""
    cmd = ["mavis-providers", "call", prompt]
    if provider:
        cmd += ["--provider", provider]
    if model:
        cmd += ["--model", model]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return f"[ERROR] {result.stderr.strip()}"
    return result.stdout.strip()


def chain(prompt: str) -> dict:
    """Show the full fallback chain test result."""
    result = subprocess.run(
        ["mavis-providers", "chain"],
        capture_output=True, text=True, timeout=10,
    )
    print(result.stdout)
    return {"prompt": prompt, "chain": "see above"}


def main():
    print("=" * 60)
    print("EXAMPLE 1: Auto-route (default = free model)")
    print("=" * 60)
    print(call("What is Mavis? 1 sentence in French."))
    print()

    print("=" * 60)
    print("EXAMPLE 2: Force Groq (fastest)")
    print("=" * 60)
    print(call("Hello in 1 word", provider="groq", model="llama-3.3-70b-versatile"))
    print()

    print("=" * 60)
    print("EXAMPLE 3: Force Claude Opus 5 (via Copilot)")
    print("=" * 60)
    print(call("Explain quantum entanglement in 1 sentence.", provider="copilot", model="claude-opus-5"))
    print()

    print("=" * 60)
    print("EXAMPLE 4: Show fallback chain")
    print("=" * 60)
    chain("anything")


if __name__ == "__main__":
    main()
