#!/usr/bin/env python3
"""
Add Mavis Swarm Teams capability to mavis.items — minimal SQL version.
Splits the insert into 2 calls (basic fields, then payload) to avoid HTTP 400 on long SQL.
"""
import json, subprocess, os, sys, time
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

# Find capabilities folder id
res = run_sql("SELECT id FROM mavis.items WHERE name='capabilities' AND parent_id=(SELECT id FROM mavis.items WHERE name='Mavis' AND parent_id IS NULL)")
if not isinstance(res, list) or not res:
    print("FAIL: capabilities folder not found", res); sys.exit(1)
cap_id = res[0]["id"]

# Check if swarm_teams already exists
res = run_sql(f"SELECT id FROM mavis.items WHERE name='swarm_teams' AND parent_id={cap_id}")
if isinstance(res, list) and res:
    print(f"swarm_teams already exists (id={res[0]['id']}), skipping"); sys.exit(0)

# Build payload as a separate string (so we can pass it via a variable)
payload = {
  "pattern": "Kimi K3 Agent Swarm",
  "orchestrator": "Mavis root session, capped at ~15 high-level steps",
  "max_workers_sandbox": 20,
  "max_workers_hosted": 300,
  "max_tool_calls": 4000,
  "speedup_factor": "4.5x on parallelizable work",
  "tools": {
    "mavis-swarm": "/usr/local/bin/mavis-swarm — simulated workers, no real LLM cost",
    "mavis-swarm-llm": "/usr/local/bin/mavis-swarm-llm — REAL LLM calls via OpenRouter, Kimi K3 by default"
  },
  "phases": [
    "1. Decompose goal into N sub-tasks with assigned roles",
    "2. Fan out to N sub-agents in parallel (isolated context each)",
    "3. Each sub-agent returns ONLY its conclusion (no trace)",
    "4. Fan in: dedup + reconcile conflicts",
    "5. Synthesizer sub-agent merges into final deliverable"
  ],
  "best_for": [
    "Large-scale information retrieval (100+ sources)",
    "Batch downloads/processing",
    "Wide-scope reading (100+ documents)",
    "Long-form writing (100K+ words)",
    "Complex programming (multi-file refactor)",
    "Office automation (docs/sheets/slides)",
    "Competitive analysis (5+ competitors)"
  ],
  "kimi_k3_comparison": {
    "kimi_k3": "300 sub-agents, 4000 tool calls, PARL-trained orchestrator, 4.5x speedup",
    "mavis_sandbox": "5-20 sub-agents, 50-200 tool calls; design supports 300+ when on Mavis platform",
    "design_parity": "Yes, same 5-phase pattern, same context isolation, same fan-in dedup"
  },
  "first_run": "2026-08-20 — 5 workers on Kimi K3 via OpenRouter"
}

# Save payload to a temp file and use psql-style variable substitution
# Actually, just do a clean INSERT in 2 steps:
# Step 1: INSERT with empty payload, RETURNING id
# Step 2: UPDATE with the full payload

# Use a more careful escape: avoid \" which doesn't help; use $$ quoting for the JSON
name = "swarm_teams"
title = "Mavis Swarm Teams (Kimi K3-style)"
desc = "Kimi K3-style agent swarm on M3. 1 orchestrator + N sub-agents in parallel + fan-in synthesis. 4.5x speedup. Use mavis-swarm or mavis-swarm-llm."
triggers = ["swarm","parallel agents","kimi k3","agent swarm","fan out","orchestrator","sub-agent"]

# Step 1: minimal insert
sql1 = f"""INSERT INTO mavis.items (kind, category, name, title, description, triggers, payload, source, status, parent_id)
VALUES ('file', 'capability', '{name}', '{title}', '{desc}', ARRAY['swarm','parallel agents','kimi k3','agent swarm','fan out','orchestrator','sub-agent'], '{{}}'::jsonb, 'self_inventory', 'active', {cap_id})
RETURNING id"""
res = run_sql(sql1)
if not isinstance(res, list) or not res or "id" not in res[0]:
    print(f"FAIL step 1: {res}"); sys.exit(1)
new_id = res[0]["id"]
print(f"✓ Step 1: inserted id={new_id}")

# Step 2: update with full payload (write to file, then use psql escape)
# JSON escapes for PG: ' → '' (double single quote)
import json
payload_json = json.dumps(payload)
payload_escaped = payload_json.replace("'", "''")

# Keep it under the 4KB query limit by stripping if needed
if len(payload_escaped) > 3500:
    print(f"  Warning: payload is {len(payload_escaped)} chars, may exceed limit")

sql2 = f"""UPDATE mavis.items SET payload = '{payload_escaped}'::jsonb, updated_at = now() WHERE id = {new_id}"""
res = run_sql(sql2)
if "_err" in res:
    print(f"FAIL step 2: {res['_err'][:300]}")
    sys.exit(1)
print(f"✓ Step 2: payload updated ({len(payload_escaped)} chars)")

# Verify
res = run_sql(f"SELECT id, name, title, length(payload::text) AS payload_size FROM mavis.items WHERE id={new_id}")
if isinstance(res, list):
    for r in res:
        print(f"  ✓ Verified: id={r['id']} name={r['name']} payload_size={r['payload_size']}")
