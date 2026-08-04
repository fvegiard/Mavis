#!/usr/bin/env python3
"""
mavis-vectorize-extra.py — Migrate OTHER text-bearing Supabase tables into mavis_knowledge.

Tables migrated (text fields extracted, concatenated, embedded, upserted as new mavis_knowledge rows):
- mavis_tasks         → type=pattern, topic="task-{short_id}", content = title + prompt + result
- mavis_alerts        → type=gotcha, topic="alert-{id}",    content = severity + action + msg
- mavis_state_snapshots → type=decision, topic="state-{id}", content = ts + kind + flattened state JSON
- mavis_cron          → type=howto,  topic="cron-{name}",   content = name + schedule + prompt

Tables skipped (no useful text / contains secrets / empty):
- mavis_provider_keys  (contains encrypted secrets)
- mavis_sessions       (mostly metadata)
- mavis_artifacts      (0 rows)
- mavis_browser_actions (0 rows)
- mavis_terminal_log   (0 rows)

Idempotent: rows with topic starting with "task-", "alert-", "state-", "cron-" are
skipped on re-run. Safe to call daily.

Usage:
  mavis-vectorize-extra            # migrate everything
  mavis-vectorize-extra --dry-run  # show what would be done, no writes
  mavis-vectorize-extra --table mavis_tasks
"""
import argparse
import importlib.util
import json
import os
import urllib.parse
import urllib.request

# Reuse helpers from mavis-vectorize.py
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("mavis_vectorize", os.path.join(SCRIPT_DIR, "mavis-vectorize.py"))
mv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv)


# Topic prefixes (used as marker so re-runs are idempotent)
PREFIXES = {
    "mavis_tasks": "task-",
    "mavis_alerts": "alert-",
    "mavis_state_snapshots": "state-",
    "mavis_cron": "cron-",
}


def row_to_text(table: str, row: dict) -> tuple[str, str]:
    """Convert one source row to (topic, content) for mavis_knowledge.

    Returns (topic, content) — topic is the marker for idempotency.
    """
    if table == "mavis_tasks":
        short_id = row.get("id", "")[:8]
        topic = f"task-{short_id}"
        content_parts = []
        if row.get("title"):
            content_parts.append(f"# {row['title']}")
        if row.get("prompt"):
            content_parts.append(f"Prompt: {row['prompt']}")
        if row.get("result"):
            content_parts.append(f"Result: {row['result']}")
        if row.get("status"):
            content_parts.append(f"Status: {row['status']}")
        if row.get("tool"):
            content_parts.append(f"Tool: {row['tool']}")
        if row.get("error"):
            content_parts.append(f"Error: {row['error']}")
        if row.get("metadata") and isinstance(row["metadata"], dict) and row["metadata"]:
            content_parts.append(f"Metadata: {json.dumps(row['metadata'], ensure_ascii=False)}")
        return topic, "\n".join(content_parts)

    if table == "mavis_alerts":
        topic = f"alert-{row.get('id', '')}"
        parts = []
        if row.get("severity"):
            parts.append(f"Severity: {row['severity']}")
        if row.get("action"):
            parts.append(f"Action: {row['action']}")
        if row.get("msg"):
            parts.append(f"Message: {row['msg']}")
        if row.get("source"):
            parts.append(f"Source: {row['source']}")
        if row.get("ts"):
            parts.append(f"Timestamp: {row['ts']}")
        return topic, "\n".join(parts)

    if table == "mavis_state_snapshots":
        topic = f"state-{row.get('id', '')}"
        parts = []
        if row.get("ts"):
            parts.append(f"Timestamp: {row['ts']}")
        if row.get("kind"):
            parts.append(f"Kind: {row['kind']}")
        # state is a JSON object — flatten it for embedding
        state = row.get("state")
        if isinstance(state, dict):
            for k, v in state.items():
                if isinstance(v, list):
                    parts.append(f"{k}: {', '.join(str(x) for x in v)}")
                else:
                    parts.append(f"{k}: {v}")
        elif isinstance(state, str):
            parts.append(f"State: {state}")
        return topic, "\n".join(parts)

    if table == "mavis_cron":
        topic = f"cron-{row.get('id', '')}"
        parts = []
        if row.get("name"):
            parts.append(f"Name: {row['name']}")
        if row.get("schedule"):
            parts.append(f"Schedule: {row['schedule']}")
        if row.get("prompt"):
            parts.append(f"Prompt: {row['prompt']}")
        if row.get("enabled") is not None:
            parts.append(f"Enabled: {row['enabled']}")
        if row.get("last_status"):
            parts.append(f"Last status: {row['last_status']}")
        return topic, "\n".join(parts)

    raise ValueError(f"unknown table {table}")


def get_existing_topics(prefix: str) -> set:
    """Return set of mavis_knowledge.topic values starting with the given prefix."""
    rows = mv.supa_get("mavis_knowledge", {"select": "topic", "topic": f"like.{prefix}%", "limit": 500})
    return {r["topic"] for r in rows}


def migrate_table(table: str, dry_run: bool = False, verbose: bool = True) -> tuple[int, int]:
    """Migrate one source table. Returns (inserted, skipped)."""
    prefix = PREFIXES[table]
    type_for_table = {
        "mavis_tasks": "pattern",
        "mavis_alerts": "gotcha",
        "mavis_state_snapshots": "decision",
        "mavis_cron": "howto",
    }[table]

    # 1. Fetch source rows
    rows = mv.supa_get(table, {"select": "*", "limit": 500})
    if verbose:
        print(f"\n# {table}: {len(rows)} source rows")

    # 2. Fetch existing topics with this prefix (for idempotency)
    existing = get_existing_topics(prefix) if not dry_run else set()
    if verbose:
        print(f"  existing mavis_knowledge topics with prefix '{prefix}': {len(existing)}")

    inserted, skipped, failed = 0, 0, 0
    for r in rows:
        topic, content = row_to_text(table, r)
        if not content.strip():
            if verbose:
                print(f"  [{topic}] empty content, skip")
            skipped += 1
            continue
        if topic in existing:
            if verbose:
                print(f"  [{topic}] already embedded, skip")
            skipped += 1
            continue

        if dry_run:
            if verbose:
                print(f"  [{topic}] DRY-RUN: would embed {len(content)} chars (type={type_for_table})")
            inserted += 1
            continue

        # 3. Embed
        try:
            vec = mv.openai_embed(content)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            if verbose:
                print(f"  [{topic}] embed ERR: {e}")
            failed += 1
            continue

        # 4. POST to mavis_knowledge
        body = {
            "topic": topic,
            "type": type_for_table,
            "content": content,
            "tags": [table.replace("mavis_", ""), "migrated", "2026-08-04"],
            "confidence": 0.8,
            "embedding": json.dumps(vec),
        }
        try:
            mv.supa_post("mavis_knowledge", body)
            if verbose:
                print(f"  [{topic}] ok ({len(content)} chars, {len(vec)}d)")
            inserted += 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            if verbose:
                print(f"  [{topic}] POST ERR: {e}")
            failed += 1

    if verbose:
        print(f"  -> inserted={inserted}, skipped={skipped}, failed={failed}")
    return inserted, skipped


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Show what would be done, no writes")
    p.add_argument("--table", choices=list(PREFIXES.keys()), help="Migrate only one table")
    args = p.parse_args()

    print("# mavis-vectorize-extra — migrate other Supabase tables into mavis_knowledge")
    print(f"# mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"# OpenRouter: {'YES' if mv.OPENROUTER_KEY else 'NO (using OpenAI)'}")
    print(f"# OpenAI: {'YES' if mv.OPENAI_KEY else 'NO'}")

    tables = [args.table] if args.table else list(PREFIXES.keys())
    total_in, total_sk = 0, 0
    for t in tables:
        ins, sk = migrate_table(t, dry_run=args.dry_run)
        total_in += ins
        total_sk += sk

    print(f"\n# Total: inserted={total_in}, skipped={total_sk}")
    if args.dry_run:
        print("# (dry-run, no actual changes)")


if __name__ == "__main__":
    main()
