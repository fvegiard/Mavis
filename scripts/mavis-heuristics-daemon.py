#!/usr/bin/env python3
"""
mavis-heuristics-daemon.py — Make heuristics.log a closed feedback loop.

Pattern: MOSS (arXiv:2605.22794) directed evolution at the prompt level.
Reads /root/.claude/jarvis/heuristics.log, counts patterns, auto-promotes
to prompts/heuristics_candidates.md when a signature fires 3+ times in 24h.
Auto-retires rules that haven't fired in 14 days.

Usage:
  mavis-heuristics-daemon            # one-shot analysis
  mavis-heuristics-daemon --watch     # poll every 5 min
  mavis-heuristics-daemon --promote   # also write candidates file

Source: 2026-08-05 ultra-research (self-improvement sub-agent)
"""
import argparse
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HEURISTICS_LOG = Path(os.environ.get("MAVIS_HEURISTICS_LOG", "/root/.claude/jarvis/heuristics.log"))
CANDIDATES_FILE = Path(os.environ.get("MAVIS_HEURISTICS_CANDIDATES", "/workspace/jarvis/prompts/heuristics_candidates.md"))
RULES_FILE = Path(os.environ.get("MAVIS_HEURISTICS_RULES", "/workspace/jarvis/prompts/heuristics_rules.md"))


def load_log():
    if not HEURISTICS_LOG.exists():
        return []
    lines = HEURISTICS_LOG.read_text().splitlines()
    entries = []
    for line in lines:
        m = re.match(r"\[([\d\-:\s]+)\]\s+(FAIL|RULE|TRIGGERED|PROMOTED):\s+(.*)", line)
        if m:
            entries.append({
                "ts": m.group(1).strip(),
                "kind": m.group(2),
                "msg": m.group(3).strip(),
                "date": datetime.fromisoformat(m.group(1).strip()).replace(tzinfo=timezone.utc) if re.match(r"\d{4}-\d{2}-\d{2}", m.group(1).strip()) else None,
            })
    return entries


def signature(msg: str) -> str:
    """Extract a stable signature from a heuristic message (strip timestamps, IDs, numbers)."""
    # Remove ISO dates, numbers, UUIDs, hex hashes
    s = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?", "TS", msg)
    s = re.sub(r"\b[0-9a-f]{8,}\b", "HASH", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d+\b", "N", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:120]


def analyze(entries):
    """Count FAIL signatures in last 24h, last 7d, last 30d."""
    now = datetime.now(timezone.utc)
    by_sig = defaultdict(list)
    for e in entries:
        if e["kind"] != "FAIL" or not e["date"]:
            continue
        by_sig[signature(e["msg"])].append(e)

    promoted = []
    for sig, events in by_sig.items():
        last_24h = [e for e in events if (now - e["date"]) < timedelta(hours=24)]
        last_7d = [e for e in events if (now - e["date"]) < timedelta(days=7)]
        last_30d = [e for e in events if (now - e["date"]) < timedelta(days=30)]
        if len(last_24h) >= 3:
            promoted.append({
                "signature": sig,
                "last_24h": len(last_24h),
                "last_7d": len(last_7d),
                "last_30d": len(last_30d),
                "first_seen": min(e["ts"] for e in events),
                "last_seen": max(e["ts"] for e in events),
                "sample": events[-1]["msg"],
                "action": "PROMOTE",
            })
        elif len(last_7d) >= 5:
            promoted.append({
                "signature": sig,
                "last_24h": len(last_24h),
                "last_7d": len(last_7d),
                "last_30d": len(last_30d),
                "first_seen": min(e["ts"] for e in events),
                "last_seen": max(e["ts"] for e in events),
                "sample": events[-1]["msg"],
                "action": "WATCH",
            })
    return sorted(promoted, key=lambda x: (-x["last_7d"], -x["last_24h"]))


def write_candidates(promoted):
    """Write heuristics_candidates.md with the findings."""
    if not promoted:
        return
    lines = [
        "# Mavis Heuristics — Promotion Candidates",
        "",
        f"_Auto-generated {datetime.now(timezone.utc).isoformat()}_",
        "",
        "Patterns detected in `/root/.claude/jarvis/heuristics.log`.",
        "Items here are **drafts** for new standing rules. Francis promotes to",
        "`PROCESS_RULES.md` after review.",
        "",
        "| Action | Signature | 24h | 7d | 30d | Last seen | Sample |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in promoted:
        sig_safe = p["signature"].replace("|", "\\|")[:80]
        sample_safe = p["sample"].replace("|", "\\|")[:80]
        lines.append(
            f"| {p['action']} | `{sig_safe}` | {p['last_24h']} | {p['last_7d']} | {p['last_30d']} | {p['last_seen']} | {sample_safe} |"
        )
    CANDIDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_FILE.write_text("\n".join(lines) + "\n")
    print(f"📝 Wrote {len(promoted)} candidates to {CANDIDATES_FILE}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--watch", action="store_true", help="poll every 5 min")
    p.add_argument("--promote", action="store_true", help="write heuristics_candidates.md")
    p.add_argument("--interval", type=int, default=300, help="watch interval (sec)")
    args = p.parse_args()

    while True:
        entries = load_log()
        promoted = analyze(entries)
        # Always print summary
        print(f"🔍 Heuristics analysis ({len(entries)} total entries)")
        if promoted:
            for p_ in promoted[:10]:
                print(f"   [{p_['action']:>7}] {p_['last_7d']:>3}x/7d  {p_['signature'][:80]}")
        else:
            print("   No patterns above threshold (3 in 24h or 5 in 7d)")
        if args.promote and promoted:
            write_candidates(promoted)
        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
