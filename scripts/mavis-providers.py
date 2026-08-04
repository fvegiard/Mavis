#!/usr/bin/env python3
"""
mavis-providers.py — Multi-provider LLM router for Mavis.

The TOP 1% agentic systems (Cursor, Devin, Claude Code) all support
multiple model providers with auto-fallback. This is Mavis's version:

  - Tests all available providers (Claude OAuth, Copilot, Groq, OpenRouter, Ollama, etc.)
  - Returns the best fallback chain
  - Auto-routes to the fastest/cheapest available

Discovered 2026-08-04: GitHub Copilot API gives access to Claude Opus 5,
Sonnet 5, Fable 5, Gemini 3.1 Pro, GPT-5.5, Grok 4.5, Kimi K2.7 (264K-400K
context each) — all in one endpoint.

Usage:
  mavis-providers test                    # test all providers
  mavis-providers chain                   # show the best fallback chain
  mavis-providers call "prompt"           # call via the best available
  mavis-providers call --provider copilot "prompt"  # force a provider
  mavis-providers list                    # show all models available per provider
"""
import sys
import os
import json
import argparse
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time


# ============================================================
# Provider definitions
# ============================================================

PROVIDERS = {
    "claude-oauth": {
        "name": "Claude (OAuth pool)",
        "env_key": "ANTHROPIC_OAUTH_TOKEN",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "auth_header": "Bearer {key}",
        "format": "anthropic",
        "models": [
            "claude-haiku-4-5", "claude-sonnet-4-6", "claude-sonnet-5",
            "claude-opus-4-6", "claude-opus-4-7", "claude-opus-5",
            "claude-fable-5",
        ],
        "priority": 1,  # Best (direct Anthropic)
        "context_window": 1_000_000,
    },
    "copilot": {
        "name": "GitHub Copilot (Claude/GPT/Gemini/Grok)",
        "env_key": "GITHUB_COPILOT_OAUTH",
        "endpoint": "https://api.githubcopilot.com/chat/completions",
        "auth_header": "Bearer {key}",
        "format": "openai",
        "models": [
            # Confirmed working 2026-08-04
            "claude-sonnet-5", "claude-opus-4.7", "claude-opus-4.8",
            "claude-opus-5", "claude-fable-5",
            "gpt-5-mini", "gpt-4o", "gpt-4o-mini",
            "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-3.6-flash",
            "kimi-k2.7-code",
        ],
        "priority": 2,  # Great fallback (multi-model, free)
        "context_window": 264_000,
    },
    "groq": {
        "name": "Groq (fast Llama/Mixtral)",
        "env_key": "GROQ_API_KEY",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "auth_header": "Bearer {key}",
        "format": "openai",
        "models": [
            "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "openai/gpt-oss-120b", "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
        ],
        "priority": 3,
        "context_window": 131_000,
    },
    "openrouter-free": {
        "name": "OpenRouter FREE tier (no cost, 6+ models)",
        "env_key": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "auth_header": "Bearer {key}",
        "format": "openai",
        "models": [
            # All confirmed working 2026-08-04
            "nvidia/nemotron-3-ultra-550b-a55b:free",     # 1M context!
            "nvidia/nemotron-3-super-120b-a12b:free",     # 262K
            "google/gemma-4-31b-it:free",                 # 262K
            "google/gemma-4-26b-a4b-it:free",             # 131K
            "inclusionai/ling-3.0-flash:free",            # 262K, fast
            "cohere/north-mini-code:free",                # 256K
            "nvidia/nemotron-nano-9b-v2:free",            # 128K
        ],
        "priority": 0,  # HIGHEST (no cost!)
        "context_window": 1_000_000,
    },
    "openrouter": {
        "name": "OpenRouter (multi-model)",
        "env_key": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "auth_header": "Bearer {key}",
        "format": "openai",
        "models": [
            # Paid
            "openai/gpt-4o-mini", "openai/gpt-4o", "anthropic/claude-sonnet-5",
            "google/gemini-2.5-pro", "meta-llama/llama-3.3-70b",
            # FREE (2026-08-04, confirmed working)
            "nvidia/nemotron-3-ultra-550b-a55b:free",     # 1M context!
            "nvidia/nemotron-3-super-120b-a12b:free",     # 262K
            "google/gemma-4-26b-a4b-it:free",             # 131K
            "google/gemma-4-31b-it:free",                 # 262K
            "inclusionai/ling-3.0-flash:free",            # 262K
            "cohere/north-mini-code:free",                # 256K
            "nvidia/nemotron-nano-9b-v2:free",            # 128K
        ],
        "priority": 4,
        "context_window": 1_000_000,
    },
    "ollama-cloud": {
        "name": "Ollama Cloud (Kimi/DeepSeek)",
        "env_key": "OLLAMA_CLOUD_API_KEY",
        "endpoint": "https://ollama.com/v1/chat/completions",
        "auth_header": "Bearer {key}",
        "format": "openai",
        "models": ["kimi-k3", "kimi-k2.6", "deepseek-v4-pro", "nemotron-3-nano:30b"],
        "priority": 5,
        "context_window": 128_000,
    },
    "gemini": {
        "name": "Gemini (Google AI)",
        "env_key": "GEMINI_API_KEY_ANTIGRAVITY",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        "auth_header": "",
        "format": "gemini",
        "models": [
            "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
            "gemini-2.0-flash-lite", "gemini-flash-latest",
        ],
        "priority": 6,
        "context_window": 1_000_000,
    },
}


# ============================================================
# Provider health testing
# ============================================================

def test_provider(name: str, p: dict) -> dict:
    """Test if a provider is available and has a working key."""
    key = os.environ.get(p["env_key"], "")
    if not key:
        return {"name": name, "available": False, "reason": f"no {p['env_key']} in env"}

    # Pick a cheap test model
    # For providers with many models, prefer a known-cheap one
    if name == "copilot":
        test_model = "gpt-4o-mini"  # Copilot's default works
    elif name == "groq":
        test_model = "llama-3.1-8b-instant"  # Cheapest Groq
    else:
        test_model = p["models"][0] if p["models"] else None
    if not test_model:
        return {"name": name, "available": False, "reason": "no models"}

    try:
        if p["format"] == "openai":
            payload = json.dumps({
                "model": test_model,
                "messages": [{"role": "user", "content": "OK"}],
                "max_tokens": 5,
            }).encode()
            url = p["endpoint"]
            headers = {
                "Content-Type": "application/json",
                "Authorization": p["auth_header"].format(key=key),
            }
        elif p["format"] == "anthropic":
            payload = json.dumps({
                "model": test_model,
                "max_tokens": 5,
                "thinking": {"type": "disabled"},
                "system": [{"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."}],
                "messages": [{"role": "user", "content": "OK"}],
            }).encode()
            url = p["endpoint"]
            headers = {
                "Content-Type": "application/json",
                "Authorization": p["auth_header"].format(key=key),
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "oauth-2025-04-20,claude-code-20250219",
            }
        elif p["format"] == "gemini":
            url = p["endpoint"].format(model=test_model, key=key)
            payload = json.dumps({"contents": [{"parts": [{"text": "OK"}]}]}).encode()
            headers = {"Content-Type": "application/json"}
        else:
            return {"name": name, "available": False, "reason": f"unknown format {p['format']}"}

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        # Add user-agent to avoid Cloudflare bot detection (Groq uses CF)
        req.add_header("User-Agent", "Mavis/5.0 (compatible; +https://MiniMax.local/mavis)")
        started = time.time()
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            latency = time.time() - started
        data = json.loads(body)

        # Check for error
        if "error" in data and "choices" not in data:
            err = data["error"]
            msg = err.get("message", str(err))[:80] if isinstance(err, dict) else str(err)[:80]
            return {"name": name, "available": False, "reason": f"API error: {msg}", "latency_ms": int(latency*1000)}

        return {
            "name": name, "available": True,
            "test_model": test_model,
            "latency_ms": int(latency * 1000),
            "model_count": len(p["models"]),
            "priority": p["priority"],
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        return {"name": name, "available": False, "reason": f"HTTP {e.code}: {body[:80]}", "latency_ms": -1}
    except Exception as e:
        return {"name": name, "available": False, "reason": f"{type(e).__name__}: {str(e)[:80]}", "latency_ms": -1}


def test_all_providers() -> list:
    """Test all providers in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(test_provider, name, p): name for name, p in PROVIDERS.items()}
        for fut in as_completed(futures):
            results.append(fut.result())
    return sorted(results, key=lambda x: (not x.get("available", False), x.get("priority", 99)))


def cmd_test(args):
    print("🩺 Testing all Mavis providers in parallel...")
    print()
    results = test_all_providers()
    print(f"{'Provider':<25} {'Status':<10} {'Latency':<12} {'Models':<8} Detail")
    print("-" * 90)
    for r in results:
        if r.get("available"):
            print(f"  {r['name']:<22} ✅ OK      {r.get('latency_ms', -1):>6}ms    {r.get('model_count', 0):>4}    via {r.get('test_model', '?')}")
        else:
            print(f"  {PROVIDERS[r['name']]['name']:<22} ❌ NO     {'-':>7}    {'-':>4}    {r.get('reason', '?')}")
    print()
    available = [r["name"] for r in results if r.get("available")]
    print(f"✅ {len(available)}/{len(results)} providers available: {', '.join(available)}")
    return 0


def cmd_chain(args):
    """Show the recommended fallback chain."""
    results = test_all_providers()
    available = [r for r in results if r.get("available")]
    print("🔗 Mavis fallback chain (best to worst):")
    print()
    for i, r in enumerate(available, 1):
        p = PROVIDERS[r["name"]]
        print(f"   {i}. {p['name']} (priority={r.get('priority', '?')}, latency={r.get('latency_ms', '?')}ms, {r.get('model_count', '?')} models)")
    print()
    if available:
        print(f"   Default: {PROVIDERS[available[0]['name']]['name']}")
    return 0


def cmd_list(args):
    """List all available models per provider."""
    for name, p in PROVIDERS.items():
        key = os.environ.get(p["env_key"], "")
        available = bool(key)
        marker = "✅" if available else "❌"
        print(f"{marker} {p['name']} ({name})")
        if available and args.verbose:
            for m in p["models"]:
                print(f"     - {m}")
        elif available:
            print(f"     {len(p['models'])} models available (use --verbose to see)")
        else:
            print(f"     (no {p['env_key']} in env)")
    return 0


def cmd_call(args):
    """Call a model via the specified or best provider."""
    if args.provider:
        if args.provider not in PROVIDERS:
            print(f"[ERROR] Unknown provider: {args.provider}", file=sys.stderr)
            print(f"   Available: {', '.join(PROVIDERS.keys())}", file=sys.stderr)
            return 1
        provider_name = args.provider
    else:
        # Auto-pick best
        results = test_all_providers()
        available = [r for r in results if r.get("available")]
        if not available:
            print("[ERROR] No providers available", file=sys.stderr)
            return 1
        provider_name = available[0]["name"]

    p = PROVIDERS[provider_name]
    key = os.environ.get(p["env_key"], "")
    if not key:
        print(f"[ERROR] No {p['env_key']} in env", file=sys.stderr)
        return 1

    # Pick model
    model = args.model or p["models"][0]

    # Build request based on format
    if p["format"] == "openai":
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": args.tokens,
        }).encode()
        url = p["endpoint"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": p["auth_header"].format(key=key),
        }
    elif p["format"] == "anthropic":
        payload = json.dumps({
            "model": model,
            "max_tokens": args.tokens,
            "thinking": {"type": "disabled"},
            "system": [{"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."}],
            "messages": [{"role": "user", "content": args.prompt}],
        }).encode()
        url = p["endpoint"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": p["auth_header"].format(key=key),
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "oauth-2025-04-20,claude-code-20250219",
        }
    elif p["format"] == "gemini":
        url = p["endpoint"].format(model=model, key=key)
        payload = json.dumps({"contents": [{"parts": [{"text": args.prompt}]}]}).encode()
        headers = {"Content-Type": "application/json"}
    else:
        print(f"[ERROR] Unsupported format: {p['format']}", file=sys.stderr)
        return 1

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        # User-Agent needed for Cloudflare (Groq) and Copilot auth
        req.add_header("User-Agent", "Mavis/5.0 (compatible; +https://MiniMax.local/mavis)")
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
        data = json.loads(body)

        if p["format"] == "openai":
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        elif p["format"] == "anthropic":
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
        elif p["format"] == "gemini":
            content = ""
            for c in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                content += c.get("text", "")

        print(content)
        if args.verbose:
            print(f"\n# via {p['name']} ({model})", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test", help="Test all providers")
    sub.add_parser("chain", help="Show fallback chain")
    p_l = sub.add_parser("list", help="List available models per provider")
    p_l.add_argument("--verbose", "-v", action="store_true")

    p_c = sub.add_parser("call", help="Call a model")
    p_c.add_argument("prompt", help="Prompt to send")
    p_c.add_argument("--provider", help="Force a specific provider")
    p_c.add_argument("--model", help="Model to use (default: first available)")
    p_c.add_argument("--tokens", type=int, default=1024)
    p_c.add_argument("--verbose", "-v", action="store_true")

    args = p.parse_args()
    cmds = {
        "test": cmd_test,
        "chain": cmd_chain,
        "list": cmd_list,
        "call": cmd_call,
    }
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
