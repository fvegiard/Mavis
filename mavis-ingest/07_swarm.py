#!/usr/bin/env python3
"""
Add Mavis Swarm Teams capability to mavis.items.
Idempotent: skips if already present.
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
            print(f"  [429] backoff {wait}s...", flush=True)
            time.sleep(wait); continue
        return {"_err": r.stderr[:500]}
    return {"_err": "max retries"}

# Find capabilities folder id
res = run_sql("""SELECT id FROM mavis.items WHERE name='capabilities' AND parent_id=(SELECT id FROM mavis.items WHERE name='Mavis' AND parent_id IS NULL)""")
if not isinstance(res, list) or not res:
    print("FAIL: capabilities folder not found", res); sys.exit(1)
cap_id = res[0]["id"]
print(f"capabilities folder id: {cap_id}")

# Check if swarm_teams already exists
res = run_sql(f"SELECT id FROM mavis.items WHERE name='swarm_teams' AND parent_id={cap_id}")
if isinstance(res, list) and res:
    print("swarm_teams already exists, skipping insert")
    sys.exit(0)

# Insert the swarm_teams capability
name = "swarm_teams"
desc = "Kimi K3-style agent swarm on the M3 platform. 1 orchestrator (capped at ~15 steps) + N sub-agents running in parallel + fan-in synthesis. 4.5x speedup on parallelizable work. Use mavis-swarm (simulated) or mavis-swarm-llm (real LLM via OpenRouter)."
title = "Mavis Swarm Teams (Kimi K3-style)"
triggers = ["swarm", "parallel agents", "kimi k3", "agent swarm", "fan out", "many subagents", "orchestrator"]
payload = {
  "pattern": "Kimi K3 Agent Swarm",
  "orchestrator": "Mavis (root session) — capped at ~15 high-level steps",
  "max_workers_sandbox": 20,
  "max_workers_hosted": 300,
  "max_tool_calls": 4000,
  "speedup_factor": "4.5x on parallelizable work",
  "tools": {
    "mavis-swarm":     "/usr/local/bin/mavis-swarm → /workspace/mavis-swarm/mavis-swarm.py (simulated workers, no real LLM cost)",
    "mavis-swarm-llm": "/usr/local/bin/mavis-swarm-llm → /workspace/mavis-swarm/test-llm.py (REAL LLM calls via OpenRouter, Kimi K3 by default)"
  },
  "sub_agent_types": [
    "research", "comparison", "risks", "examples", "synthesis",
    "numbers", "people", "tools", "critique", "future", "verifier"
  ],
  "supported_models": [
    "moonshotai/kimi-k3 (Kimi K3 Swarm, default)",
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.1-70b-instruct",
    "any OpenRouter model (openrouter.ai/api/v1/models)"
  ],
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
    "kimi_k3": "300 sub-agents, 4000 tool calls, PARL-trained orchestrator, 4.5x speedup (K2.6+ ceiling, served by K3)",
    "mavis_sandbox": "5-20 sub-agents, 50-200 tool calls, design supports 300+ (when run on Mavis platform with VM access)",
    "design_parity": "Yes — same 5-phase pattern, same context isolation, same fan-in dedup. The bottleneck is the runtime, not the design."
  },
  "first_run": "2026-08-20 — verified 5 workers on Kimi K3 via OpenRouter, real LLM calls in parallel"
}
payload_json = json.dumps(payload).replace("'", "''")
desc_sql = desc.replace("'", "''")
title_sql = title.replace("'", "''")
triggers_arr = "{" + ",".join('"' + t.replace('"', '\\"') + '"' for t in triggers) + "}"

sql = (
    f"INSERT INTO mavis.items (kind, category, name, title, description, triggers, payload, source, status, parent_id) "
    f"VALUES ('capability', 'capability', '{name}', '{title_sql}', '{desc_sql}', '{triggers_arr}'::text[], "
    f"'{payload_json}'::jsonb, 'self_inventory', 'active', {cap_id})"
)
res = run_sql(sql)
if "_err" in res:
    print(f"FAIL: {res['_err'][:300]}")
    sys.exit(1)
print(f"✓ Inserted /Mavis/capabilities/swarm_teams")

# Verify
res = run_sql(f"SELECT id, name, title FROM mavis.items WHERE name='swarm_teams'")
if isinstance(res, list):
    for r in res:
        print(f"  id={r['id']} name={r['name']} title={r['title']}")
