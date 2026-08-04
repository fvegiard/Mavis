#!/usr/bin/env python3
"""
mavis-stream.py — Streaming output for Mavis.

The top 1% agents stream responses (Devin, Claude Code, Cursor). This
adds streaming to mavis-call so Mavis feels as responsive as the top
agents, and reduces time-to-first-token from ~10s to <1s.

Usage:
  mavis-stream "Tell me a story about Mavis the agent"
  mavis-stream --model claude-sonnet-5 "Architecture review"
  echo "q" | mavis-stream
"""
import argparse
import json
import os
import subprocess
import sys


def stream_via_curl(prompt: str, model: str = "claude-haiku-4-5", system: str = "", tokens: int = 1024):
    """Stream using curl + SSE parsing. No extra dependencies."""
    oauth = os.environ.get("ANTHROPIC_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    if not oauth:
        print("[ERROR] ANTHROPIC_OAUTH_TOKEN or ANTHROPIC_API_KEY required", file=sys.stderr)
        return 1

    url = "https://api.anthropic.com/v1/messages"
    headers = [
        "-H", "content-type: application/json",
        "-H", "Authorization: Bearer " + oauth,
        "-H", "anthropic-version: 2023-06-01",
        "-H", "anthropic-beta: oauth-2025-04-20,claude-code-20250219",
        "-H", "accept: text/event-stream",
        "-H", "User-Agent: Mavis/5.0",  # required by Cloudflare edge (1010)
    ]

    # Build system array with cache_control for the static part
    system_block = []
    if system:
        system_block.append({"type": "text", "text": system, "cache_control": {"type": "ephemeral"}})
    system_block.insert(0, {"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude.", "cache_control": {"type": "ephemeral"}})

    payload = {
        "model": model,
        "max_tokens": tokens,
        "stream": True,
        "thinking": {"type": "disabled"},
        "system": system_block,
        "messages": [{"role": "user", "content": prompt}],
    }

    # Use curl --no-buffer + NDJSON-ish SSE parsing
    cmd = [
        "curl", "-sS", "--no-buffer", "-N", url,
        *headers,
        "-d", json.dumps(payload),
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    full_text = []
    for line in proc.stdout:
        line = line.rstrip("\n")
        if not line:
            continue
        if line.startswith("event:"):
            continue
        if line.startswith("data:"):
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            etype = obj.get("type", "")
            if etype == "content_block_start":
                pass
            elif etype == "content_block_delta":
                delta = obj.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        print(text, end="", flush=True)
                        full_text.append(text)
            elif etype == "message_stop":
                break
            elif etype == "error":
                err = obj.get("error", {})
                print(f"\n[ERROR] {err.get('message', '?')}", file=sys.stderr)
                return 1

    proc.wait()
    print()  # Final newline
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("prompt", nargs="?", help="The prompt to stream")
    p.add_argument("--model", default="claude-haiku-4-5")
    p.add_argument("--system", default="")
    p.add_argument("--tokens", type=int, default=1024)
    args = p.parse_args()

    prompt = args.prompt
    if not prompt:
        # Read from stdin
        prompt = sys.stdin.read().strip()

    if not prompt:
        print("Usage: mavis-stream 'prompt' or echo 'prompt' | mavis-stream", file=sys.stderr)
        return 1

    return stream_via_curl(prompt, args.model, args.system, args.tokens)


if __name__ == "__main__":
    sys.exit(main())
