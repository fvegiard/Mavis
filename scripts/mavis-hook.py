#!/usr/bin/env python3
"""
mavis-hook.py — Hooks for Mavis (pre/post tool calls).

The top 1% agents (Claude Code) have a hooks system that runs scripts
before/after tool calls. This is Mavis's version:
  - Pre-call: validate request, warn about cost, block dangerous ops
  - Post-call: log usage, update cost tracker, check for secrets

Hooks are configured via /root/.claude/jarvis/hooks.json and run automatically
by mavis-call if MAVIS_HOOKS=1.

Usage:
  mavis-hook pre --tool mavis-call --args '{"prompt":"...","model":"..."}'
  mavis-hook post --tool mavis-call --usage '{"input_tokens":1000,"output_tokens":500}'
  mavis-hook list    # show configured hooks
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

HOOKS_CONFIG = Path(os.environ.get("MAVIS_HOOKS_CONFIG", "/root/.claude/jarvis/hooks.json"))


SECRET_PATTERNS = [
    r"sk-ant-[a-zA-Z0-9-]{20,}",
    r"sk-proj-[a-zA-Z0-9-]{20,}",
    r"sk-or-v1-[a-zA-Z0-9-]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"glpat-[a-zA-Z0-9_-]{20,}",
    r"AIza[0-9A-Za-z_-]{35}",
    r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9_-]{50,}",
]

DANGEROUS_PATTERNS = [
    (r"rm\s+-rf\s+/", "Massive recursive delete from root"),
    (r"dd\s+if=", "Direct disk write"),
    (r"mkfs\.", "Filesystem format"),
    (r":\(\)\s*\{.*:\|:.*\}", "Fork bomb pattern"),
    (r"curl[^|]*\|\s*bash", "Pipe-to-bash (supply chain risk)"),
    (r"chmod\s+-R\s+777", "World-writable permissions"),
]


def load_config() -> dict:
    if not HOOKS_CONFIG.exists():
        return {"pre": [], "post": []}
    try:
        return json.loads(HOOKS_CONFIG.read_text())
    except json.JSONDecodeError:
        return {"pre": [], "post": []}


def check_secrets(text: str) -> list:
    """Return list of (pattern_name, matched_string) found in text."""
    found = []
    for pat in SECRET_PATTERNS:
        m = re.search(pat, text)
        if m:
            found.append((pat, m.group(0)[:20] + "..."))
    return found


def check_dangerous(text: str) -> list:
    """Return list of (pattern_name, description) for dangerous operations."""
    found = []
    for pat, desc in DANGEROUS_PATTERNS:
        if re.search(pat, text):
            found.append((desc, pat))
    return found


def estimate_cost(prompt: str, model: str = "claude-haiku-4-5") -> float:
    """Rough cost estimate: ~4 chars per token, input only."""
    pricing = {
        "claude-haiku-4-5": 0.80,
        "claude-sonnet-4-6": 3.00,
        "claude-sonnet-5": 5.00,
        "claude-opus-5": 25.00,
    }
    input_tokens = len(prompt) / 4
    return input_tokens * pricing.get(model, 1.0) / 1_000_000


def run_pre_hook(tool: str, args: dict) -> dict:
    """Pre-call hook: validate, warn, block if needed."""
    issues = []
    prompt = ""
    if "prompt" in args:
        prompt = args["prompt"]
    elif "system" in args:
        prompt = args.get("system", "") + " " + prompt

    # 1. Secret detection
    secrets = check_secrets(prompt)
    if secrets:
        issues.append({"severity": "BLOCK", "type": "secret", "detail": f"Found {len(secrets)} potential secret(s) in prompt"})

    # 2. Dangerous operation detection
    dangers = check_dangerous(prompt)
    if dangers:
        for desc, pat in dangers:
            issues.append({"severity": "WARN", "type": "dangerous", "detail": f"{desc} (pattern: {pat})"})

    # 3. Cost estimate
    model = args.get("model", "claude-haiku-4-5")
    cost = estimate_cost(prompt, model)
    if cost > 0.10:
        issues.append({"severity": "INFO", "type": "cost", "detail": f"Estimated cost: ${cost:.4f} (model={model})"})

    # 4. Length check
    if len(prompt) > 100_000:
        issues.append({"severity": "WARN", "type": "length", "detail": f"Prompt is {len(prompt):,} chars (>100K)"})

    return {
        "tool": tool,
        "issues": issues,
        "allow": all(i["severity"] != "BLOCK" for i in issues),
    }


def run_post_hook(tool: str, usage: dict, output: str = "") -> dict:
    """Post-call hook: log, check output for secrets."""
    issues = []

    # 1. Check output for secrets
    if output:
        secrets = check_secrets(output)
        if secrets:
            issues.append({"severity": "WARN", "type": "secret_in_output", "detail": f"Found {len(secrets)} potential secret(s) in output"})

    # 2. Log usage to cost tracker
    cost_script = "/usr/local/bin/mavis-cost"
    if os.path.exists(cost_script) and usage:
        model = usage.get("model", "claude-haiku-4-5")
        try:
            subprocess_args = [
                cost_script, "--record",
                f"model={model}",
                f"input={usage.get('input_tokens', 0)}",
                f"output={usage.get('output_tokens', 0)}",
            ]
            if usage.get("cache_read_tokens"):
                subprocess_args.append(f"cache_read={usage['cache_read_tokens']}")
            if usage.get("cache_creation_tokens"):
                subprocess_args.append(f"cache_write={usage['cache_creation_tokens']}")
            import subprocess
            subprocess.run(subprocess_args, capture_output=True, timeout=5)
        except Exception:
            pass  # Best effort

    return {"tool": tool, "issues": issues}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("pre", help="Run pre-call hooks")
    p_pre.add_argument("--tool", required=True)
    p_pre.add_argument("--args", default="{}", help="JSON string of args")

    p_post = sub.add_parser("post", help="Run post-call hooks")
    p_post.add_argument("--tool", required=True)
    p_post.add_argument("--usage", default="{}", help="JSON string of usage")
    p_post.add_argument("--output", default="", help="Tool output to scan")

    sub.add_parser("list", help="List configured hooks")

    args = p.parse_args()

    if args.cmd == "pre":
        tool_args = json.loads(args.args)
        result = run_pre_hook(args.tool, tool_args)
        print(json.dumps(result, indent=2))
        return 0 if result["allow"] else 2
    elif args.cmd == "post":
        usage = json.loads(args.usage)
        result = run_post_hook(args.tool, usage, args.output)
        print(json.dumps(result, indent=2))
        return 0
    elif args.cmd == "list":
        config = load_config()
        print(f"📋 Hooks configured at {HOOKS_CONFIG}")
        for phase in ("pre", "post"):
            print(f"   {phase}: {len(config.get(phase, []))} hook(s)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
