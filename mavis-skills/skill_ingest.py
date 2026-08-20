#!/usr/bin/env python3
"""
skill_ingest.py — Deep ingestion of skills into mavis.items.
For each skill: load SKILL.md body, extract structured summary, UPDATE mavis.items.
"""
import json, subprocess, os, sys, time
from pathlib import Path

SUPABASE_KEY = os.environ['SUPABASEMGMT_API_KEY']
REF = 'tuwshovazpqzsvwnicgj'

def run_sql(sql, retries=3, backoff=5):
    for attempt in range(retries):
        r = subprocess.run([
          "curl", "-fsS", "--max-time", "60",
          "-X", "POST",
          f"https://api.supabase.com/v1/projects/{REF}/database/query",
          "-H", "Authorization: Bearer " + SUPABASE_KEY,
          "-H", "Content-Type: application/json",
          "-d", json.dumps({"query": sql}),
        ], capture_output=True, text=True)
        if r.returncode == 0:
            if not r.stdout.strip(): return {"_ok": True}
            try: return json.loads(r.stdout)
            except: return {"_raw": r.stdout[:500]}
        if "429" in r.stderr or "rate" in r.stderr.lower():
            wait = backoff * (2 ** attempt)
            print(f"  [429] backoff {wait}s...", flush=True); time.sleep(wait); continue
        return {"_err": r.stderr[:500]}
    return {"_err": "max retries"}

def update_skill_summary(name: str, summary: dict):
    full_payload = {"summary": summary, "ingested_at": "2026-08-20", "version": "v1"}
    payload_json = json.dumps(full_payload).replace("'", "''")
    wtu = "; ".join(summary.get("when_to_use", [])[:3])[:200]
    desc = f"{summary.get('deliverable', 'Mavis skill')} — USE WHEN: {wtu}"
    desc_sql = desc.replace("'", "''")
    sql = f"""UPDATE mavis.items
SET payload = '{payload_json}'::jsonb,
    description = '{desc_sql}',
    updated_at = now()
WHERE name = '{name}' AND category = 'skill'"""
    res = run_sql(sql)
    if "_err" in res:
        return False, res["_err"][:200]
    return True, "ok"

if __name__ == "__main__":
    src = Path('/workspace/mavis-skills/skill_summaries.json')
    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)
    SUMMARIES = json.loads(src.read_text())
    print(f"Loaded {len(SUMMARIES)} summaries from {src}")
    ok, err = 0, 0
    for name, summary in SUMMARIES.items():
        success, msg = update_skill_summary(name, summary)
        if success:
            ok += 1
            print(f"  ✓ {name}")
        else:
            err += 1
            print(f"  ✗ {name}: {msg[:100]}")
        time.sleep(0.3)  # rate limit
    print(f"\n{ok} updated, {err} errors")
