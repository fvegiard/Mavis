#!/usr/bin/env python3
"""
mavis-a2a.py — Agent-to-Agent (A2A) protocol for Mavis.

The 2026 top agentic platforms (Google A2A, LangGraph, CrewAI) all support
agent-to-agent communication. This is Mavis's lightweight A2A:

  - Message envelope: {from, to, action, payload, timestamp, trace_id}
  - Actions: 'task', 'query', 'broadcast', 'handoff', 'result'
  - Persistence: Supabase mavis_sessions table (already exists)
  - Routing: by agent_name (Mavis, MaxClaw, MaxHermes, Claude-Code)

Usage:
  mavis-a2a send --to MaxHermes --action query --payload '{"q": "research X"}'
  mavis-a2a inbox                              # read messages for me
  mavis-a2a handoff --to MaxClaw --task "deploy"  # hand off a task
  mavis-a2a broadcast --action notify --payload '{}'  # to all
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SUPABASE_REF = "hzdzeleznvxzncgzqiub"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6ZHplbGV6bnZ4em5jZ3pxaXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDE0NDY0MywiZXhwIjoyMDk5NzIwNjQzfQ.Vvs_oY4dY-vDGVyxEipltGA9s3XcqhQJV4XBpVOH-i4"


def get_agent_name() -> str:
    return os.environ.get("MAVIS_AGENT", "Mavis")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def send_message(to_agent: str, action: str, payload: dict, trace_id: str | None = None) -> str:
    """Send a message to another agent via Supabase mavis_sessions / mavis_tasks."""
    trace_id = trace_id or str(uuid.uuid4())
    msg = {
        "trace_id": trace_id,
        "from": get_agent_name(),
        "to": to_agent,
        "action": action,
        "payload": payload,
        "timestamp": now_iso(),
        "status": "pending",
    }

    # Persist to a local file (always works)
    outbox = Path("/workspace/jarvis/a2a/outbox.jsonl")
    outbox.parent.mkdir(parents=True, exist_ok=True)
    with outbox.open("a") as f:
        f.write(json.dumps(msg) + "\n")

    # Try to post to Supabase (best effort)
    import urllib.request
    try:
        req = urllib.request.Request(
            f"https://{SUPABASE_REF}.supabase.co/rest/v1/mavis_sessions",
            data=json.dumps({
                "session_id": trace_id,
                "agent_name": to_agent,
                "metadata": {"a2a_from": get_agent_name(), "a2a_action": action, "a2a_payload": payload},
                "status": "pending",
            }).encode(),
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Local file is the source of truth

    return trace_id


def read_inbox() -> list:
    """Read messages for the current agent."""
    inbox = []
    # Local outbox (last seen = me or everyone)
    outbox = Path("/workspace/jarvis/a2a/outbox.jsonl")
    if outbox.exists():
        me = get_agent_name()
        for line in outbox.read_text().splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("to") == me or msg.get("to") == "*" or msg.get("to") == "all":
                inbox.append(msg)
    return inbox


def cmd_send(args):
    payload = json.loads(args.payload) if args.payload else {}
    trace_id = send_message(args.to, args.action, payload, args.trace_id)
    print(f"📤 Sent to {args.to} (action={args.action}, trace_id={trace_id[:8]})")
    return 0


def cmd_inbox(args):
    inbox = read_inbox()
    if not inbox:
        print("📭 Inbox empty")
        return 0
    print(f"📬 {len(inbox)} message(s):")
    for msg in inbox[-20:]:  # Last 20
        print(f"   {msg['timestamp']} | {msg['from']} → {msg['to']} | {msg['action']} | {msg['trace_id'][:8]}")
        if args.verbose:
            print(f"      payload: {json.dumps(msg['payload'], ensure_ascii=False)[:200]}")
    return 0


def cmd_handoff(args):
    """Hand off a task to another agent."""
    payload = {
        "task": args.task,
        "context": args.context or {},
        "priority": args.priority or "normal",
    }
    trace_id = send_message(args.to, "handoff", payload)
    print(f"🤝 Handed off to {args.to}: {args.task}")
    print(f"   trace_id: {trace_id}")
    return 0


def cmd_broadcast(args):
    payload = json.loads(args.payload) if args.payload else {}
    for target in ("Mavis", "MaxHermes", "MaxClaw", "all"):
        send_message(target, args.action, payload)
    print(f"📢 Broadcast to all agents (action={args.action})")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_s = sub.add_parser("send", help="Send a message to another agent")
    p_s.add_argument("--to", required=True)
    p_s.add_argument("--action", required=True, choices=["task", "query", "handoff", "result", "notify"])
    p_s.add_argument("--payload", default="{}", help="JSON payload")
    p_s.add_argument("--trace-id", help="Optional trace ID for correlation")

    p_i = sub.add_parser("inbox", help="Read inbox")
    p_i.add_argument("--verbose", "-v", action="store_true")

    p_h = sub.add_parser("handoff", help="Hand off a task to another agent")
    p_h.add_argument("--to", required=True)
    p_h.add_argument("--task", required=True)
    p_h.add_argument("--context", default="{}", help="JSON context")
    p_h.add_argument("--priority", choices=["low", "normal", "high", "urgent"])

    p_b = sub.add_parser("broadcast", help="Broadcast to all agents")
    p_b.add_argument("--action", required=True, choices=["notify", "sync", "alert"])
    p_b.add_argument("--payload", default="{}")

    args = p.parse_args()

    cmds = {
        "send": cmd_send,
        "inbox": cmd_inbox,
        "handoff": cmd_handoff,
        "broadcast": cmd_broadcast,
    }
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
