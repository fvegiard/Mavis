#!/usr/bin/env python3
"""
mavis-cost.py — Cost analytics for Mavis API calls.

The top 1% agents have cost dashboards (Cursor, Devin, Claude Code).
This is Mavis's cost tracker:
  - Parses mavis-call --raw output for usage
  - Computes per-model costs (Anthropic pricing 2026)
  - Logs to /workspace/jarvis/data/cost_log.json
  - Shows daily/weekly/monthly breakdown
  - Recommends cost optimizations

Usage:
  mavis-cost summary
  mavis-cost today
  mavis-cost optimize
  mavis-cost --record model=claude-sonnet-5 input=1000 output=500
"""
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Anthropic pricing (per 1M tokens, 2026-08)
PRICING = {
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_write": 1.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-5": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
    "claude-opus-5": {"input": 25.00, "output": 125.00, "cache_read": 2.50, "cache_write": 31.25},
}


COST_LOG = Path(os.environ.get("MAVIS_COST_LOG", "/workspace/jarvis/data/cost_log.json"))


def cost_for(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    """Compute USD cost for a call."""
    p = PRICING.get(model, PRICING["claude-haiku-4-5"])
    return (
        input_tokens * p["input"] / 1_000_000
        + output_tokens * p["output"] / 1_000_000
        + cache_read * p["cache_read"] / 1_000_000
        + cache_write * p["cache_write"] / 1_000_000
    )


def load_log() -> list:
    if not COST_LOG.exists():
        return []
    try:
        return json.loads(COST_LOG.read_text())
    except json.JSONDecodeError:
        return []


def save_log(entries: list):
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    COST_LOG.write_text(json.dumps(entries, indent=2))


def record(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0, label: str = ""):
    entries = load_log()
    cost = cost_for(model, input_tokens, output_tokens, cache_read, cache_write)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "input": input_tokens,
        "output": output_tokens,
        "cache_read": cache_read,
        "cache_write": cache_write,
        "cost_usd": round(cost, 6),
        "label": label,
    }
    entries.append(entry)
    save_log(entries)
    print(f"💰 Recorded: {model} | {input_tokens}+{output_tokens} tok | ${cost:.4f}")


def summarize(entries: list, period: str = "all"):
    if period == "today":
        today = datetime.now(timezone.utc).date().isoformat()
        entries = [e for e in entries if e["timestamp"].startswith(today)]
    elif period == "week":
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        entries = [e for e in entries if e["timestamp"] >= cutoff]
    elif period == "month":
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        entries = [e for e in entries if e["timestamp"] >= cutoff]

    by_model = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "cost": 0.0})
    for e in entries:
        e_cost = e.get("cost_usd", e.get("cost", 0))
        m = by_model[e["model"]]
        m["calls"] = m.get("calls", 0) + 1
        m["input"] = m.get("input", 0) + e.get("input", 0)
        m["output"] = m.get("output", 0) + e.get("output", 0)
        m["cost"] = m.get("cost", 0) + e_cost

    total_cost = sum(m["cost"] for m in by_model.values())
    total_calls = sum(m["calls"] for m in by_model.values())

    print(f"📊 Mavis cost report ({period})")
    print(f"   Total calls: {total_calls}")
    print(f"   Total cost: ${total_cost:.4f}")
    print()
    print(f"   {'Model':<25} {'Calls':>6} {'Input tok':>12} {'Output tok':>12} {'Cost':>10}")
    print(f"   {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*10}")
    for model, stats in sorted(by_model.items(), key=lambda x: -x[1]["cost"]):
        print(f"   {model:<25} {stats['calls']:>6} {stats['input']:>12} {stats['output']:>12} ${stats['cost']:>9.4f}")


def optimize(entries: list):
    """Suggest cost optimizations based on actual usage."""
    print("🔧 Mavis cost optimization recommendations")
    print()
    if not entries:
        print("   No usage data yet. Run some mavis-call first.")
        return
    total = sum(e.get("cost_usd", e.get("cost", 0)) for e in entries)
    by_model = defaultdict(lambda: {"calls": 0, "cost": 0.0})
    for e in entries:
        e_cost = e.get("cost_usd", e.get("cost", 0))
        by_model[e["model"]]["calls"] = by_model[e["model"]].get("calls", 0) + 1
        by_model[e["model"]]["cost"] = by_model[e["model"]].get("cost", 0) + e_cost

    sonnet_cost = by_model.get("claude-sonnet-5", {}).get("cost", 0) + by_model.get("claude-sonnet-4-6", {}).get("cost", 0)
    haiku_cost = by_model.get("claude-haiku-4-5", {}).get("cost", 0)
    if sonnet_cost > 0.10 and sonnet_cost > haiku_cost * 2:
        print(f"   ⚠️  Sonnet costs ${sonnet_cost:.4f} vs Haiku ${haiku_cost:.4f}")
        print("      → Consider Haiku for RAG/long-context (10x cheaper)")
    haiku_calls = by_model.get("claude-haiku-4-5", {}).get("calls", 0)
    if haiku_calls > 0:
        print(f"   ✅ Haiku 4.5 used {haiku_calls}x — already cost-optimized")
    if total > 1.0:
        print(f"   💡 Total ${total:.2f} > $1 — consider prompt caching (90% discount on cached prefix)")
        print("      mavis-call uses cache_control on system prompt by default")
    print()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    p_sum = sub.add_parser("summary", help="Show cost summary")
    p_sum.add_argument("--period", default="all", choices=["all", "today", "week", "month"])

    sub.add_parser("today", help="Show today's cost")
    sub.add_parser("week", help="Show last 7 days")
    sub.add_parser("month", help="Show last 30 days")

    sub.add_parser("optimize", help="Suggest optimizations")

    p_rec = sub.add_parser("record", help="Record a call")
    p_rec.add_argument("kv", nargs="+", help="key=value pairs: model=X input=N output=N cache_read=N cache_write=N label=Y")

    args = p.parse_args()

    entries = load_log()

    if args.cmd == "summary":
        summarize(entries, args.period)
    elif args.cmd in ("today", "week", "month"):
        summarize(entries, args.cmd)
    elif args.cmd == "optimize":
        optimize(entries)
    elif args.cmd == "record":
        kv_list = args.kv or []
        d = {}
        for kv in kv_list:
            k, v = kv.split("=", 1)
            d[k] = v
        record(
            model=d.get("model", "claude-haiku-4-5"),
            input_tokens=int(d.get("input", 0)),
            output_tokens=int(d.get("output", 0)),
            cache_read=int(d.get("cache_read", 0)),
            cache_write=int(d.get("cache_write", 0)),
            label=d.get("label", ""),
        )
    else:
        # Default: summary
        summarize(entries, "all")


if __name__ == "__main__":
    main()
