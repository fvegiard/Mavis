#!/usr/bin/env python3
"""
Mavis data ingestion — RESUME version.
- Reads current state of mavis.items to know what's already inserted
- Skips folders (14 done) and re-inserts only missing files
- Also adds the new 'vms' folder with VM access docs
"""
import json, subprocess, sys, os
from pathlib import Path

DATA = json.load(open('/workspace/mavis-ingest/03_ingest.json'))
SUPABASE_KEY = os.environ['SUPABASEMGMT_API_KEY']
REF = 'tuwshovazpqzsvwnicgj'

# New additions: VM access folder + entries
VM_ADDS = [
  {"kind": "folder", "name": "vms", "title": "VMs — MaxClaw & Hermes on MiniMax",
   "description": "Persistent VMs on Francis's MiniMax account. Mavis can communicate with them via the `communicate` tool. Use this folder as the access-pattern reference.",
   "triggers": [], "payload": {"channel": "communicate", "platform": "minimax", "owner": "Francis", "note": "These are persistent VMs, not spawned Branch sessions. They have root_session_id = their own ID."}, "source": "vm_inventory", "status": "active", "parent": "Mavis"},
  {"kind": "file", "category": "agent", "name": "maxclaw_vm", "title": "MaxClaw VM",
   "description": "MaxClaw is a persistent VM on Francis's MiniMax account (session 419690516496665). Hands-on operator: runs commands, executes code, manipulates files on remote systems. Owns the Kahnawake email extraction pipeline. Reaches Mavis + Hermes via communicate. PING with `communicate` to keep warm.",
   "triggers": ["maxclaw", "max claw", "operator vm", "kahnawake"],
   "payload": {"session_id": "419690516496665", "platform": "minimax_vm", "owner": "Francis", "tools": ["shell","code","fs","communicate"], "owner_of": ["kahnawake email pipeline"]},
   "source": "vm_inventory", "status": "active", "parent": "Mavis/vms"},
  {"kind": "file", "category": "agent", "name": "hermes_vm", "title": "Hermes VM",
   "description": "Hermes is a persistent VM on Francis's MiniMax account (session 419691001540746). Cross-agent coordinator: bridges Mavis and external systems (web search, email, IM, API). Never invents facts; cites sources. Reaches MaxClaw for shell work, Mavis for routing. PING with `communicate` to keep warm.",
   "triggers": ["hermes", "coordinator vm", "external bridge", "web search bridge"],
   "payload": {"session_id": "419691001540746", "platform": "minimax_vm", "owner": "Francis", "tools": ["web_search","email","im","api","communicate"], "guarantee": "cites sources, never invents"},
   "source": "vm_inventory", "status": "active", "parent": "Mavis/vms"},
  {"kind": "file", "category": "capability", "name": "vm_communication", "title": "VM Communication Pattern",
   "description": "How Mavis talks to MaxClaw and Hermes. Use the `communicate` tool with their session_id. The message is delivered and they respond on their own time. No need to wait synchronously — they will message back. For health checks, send a short ping.",
   "triggers": ["communicate with vm", "ping maxclaw", "ping hermes", "vm health check"],
   "payload": {
     "pattern": "communicate(to_session=<session_id>, content='<message>')",
     "maxclaw": "419690516496665",
     "hermes": "419691001540746",
     "claude": "424042951970936",
     "response_mode": "async (they reply via communicate back to me)",
     "health_check": "send a 1-line ping every 6h via cron to keep status fresh"
   },
   "source": "vm_inventory", "status": "active", "parent": "Mavis/vms"},
]
DATA.extend(VM_ADDS)

def run_sql(sql):
    r = subprocess.run([
      "curl", "-fsS", "--max-time", "60",
      "-X", "POST",
      f"https://api.supabase.com/v1/projects/{REF}/database/query",
      "-H", "Authorization: Bearer " + SUPABASE_KEY,
      "-H", "Content-Type: application/json",
      "-d", json.dumps({"query": sql}),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        return {"_err": r.stderr[:500]}
    if not r.stdout.strip():
        return {"_ok": True}
    try: return json.loads(r.stdout)
    except: return {"_raw": r.stdout[:500]}

def path_of(it):
    if it["parent"] is None: return it["name"]
    return it["parent"] + "/" + it["name"]

# ============================================================
# Step 1: get current state of mavis.items
# ============================================================
print("=== Step 1: read current state ===")
res = run_sql("SELECT id, kind, parent_id, name, (SELECT name FROM mavis.items p WHERE p.id = m.parent_id) AS parent_name, (SELECT name FROM mavis.items gp WHERE gp.id = (SELECT parent_id FROM mavis.items p2 WHERE p2.id = m.parent_id)) AS gp_name FROM mavis.items m ORDER BY id")
if not isinstance(res, list):
    print("  FAIL:", res); sys.exit(1)

# Build existing-path set
existing_paths = set()
for r in res:
    if r["kind"] == "folder" and r["parent_name"] is None:
        existing_paths.add(r["name"])
    elif r["kind"] == "folder" and r["gp_name"] is None:
        existing_paths.add(f"{r['parent_name']}/{r['name']}")
    elif r["kind"] == "folder":
        existing_paths.add(f"{r['gp_name']}/{r['parent_name']}/{r['name']}")
    elif r["kind"] == "file" and r["parent_name"]:
        existing_paths.add(f"{r['parent_name']}/{r['name']}")

# Also build path → id map for folders
folder_path_to_id = {}
for r in res:
    if r["kind"] == "folder" and r["parent_name"] is None:
        folder_path_to_id[r["name"]] = r["id"]
    elif r["kind"] == "folder" and r["gp_name"] is None:
        folder_path_to_id[f"{r['parent_name']}/{r['name']}"] = r["id"]
    elif r["kind"] == "folder":
        folder_path_to_id[f"{r['gp_name']}/{r['parent_name']}/{r['name']}"] = r["id"]

print(f"  Existing items: {len(res)} ({len(existing_paths)} unique paths)")
print(f"  Existing folders: {len(folder_path_to_id)}")

# ============================================================
# Step 2: insert any missing folders (the new vms folder)
# ============================================================
folders = [it for it in DATA if it["kind"] == "folder"]
files   = [it for it in DATA if it["kind"] == "file"]

print(f"\n=== Step 2: insert missing folders ===")
new_folders = [f for f in folders if path_of(f) not in folder_path_to_id]
print(f"  Need to insert: {len(new_folders)} new folders")
def depth(p): return p.count("/")
new_folders.sort(key=lambda f: depth(path_of(f)))
for f in new_folders:
    path = path_of(f)
    parent_id = "NULL"
    if f["parent"]:
        if f["parent"] not in folder_path_to_id:
            print(f"  ! parent missing: {path}"); continue
        parent_id = str(folder_path_to_id[f["parent"]])
    payload_json = json.dumps(f.get("payload", {})).replace("'", "''")
    desc = (f.get("description") or "").replace("'", "''")
    title = (f.get("title") or f["name"]).replace("'", "''")
    name = f["name"].replace("'", "''")
    sql = (
        f"INSERT INTO mavis.items (kind, name, title, description, payload, source, status, parent_id) "
        f"VALUES ('folder', '{name}', '{title}', '{desc}', '{payload_json}'::jsonb, "
        f"'{f.get('source','self_inventory')}', '{f.get('status','active')}', {parent_id}) RETURNING id"
    )
    res = run_sql(sql)
    if "id" in (res[0] if isinstance(res,list) else {}):
        folder_path_to_id[path] = res[0]["id"]
        print(f"  ✓ {path:50} → id={res[0]['id']}")
    else:
        print(f"  ✗ {path}: {res}")

# ============================================================
# Step 3: insert missing files
# ============================================================
print(f"\n=== Step 3: insert missing files ===")
to_insert = [f for f in files if path_of(f) not in existing_paths]
print(f"  Need to insert: {len(to_insert)} files (skipped {len(files) - len(to_insert)} already there)")

ok = 0
err = 0
for i, f in enumerate(to_insert):
    path = path_of(f)
    parent_path = f["parent"]
    if parent_path not in folder_path_to_id:
        print(f"  ! parent folder missing: {path} (parent={parent_path})"); err += 1; continue
    parent_id = folder_path_to_id[parent_path]
    payload_json = json.dumps(f.get("payload", {})).replace("'", "''")
    desc = (f.get("description") or "").replace("'", "''")
    title = (f.get("title") or f["name"]).replace("'", "''")
    name = f["name"].replace("'", "''")
    triggers_arr = "{" + ",".join('"' + t.replace('"', '\\"') + '"' for t in f.get("triggers", [])) + "}"
    category = f.get("category") or "NULL"
    if category != "NULL":
        category = "'" + category + "'"
    sql = (
        f"INSERT INTO mavis.items (kind, category, name, title, description, triggers, payload, source, status, parent_id) "
        f"VALUES ('file', {category}, '{name}', '{title}', '{desc}', '{triggers_arr}'::text[], "
        f"'{payload_json}'::jsonb, '{f.get('source','system')}', '{f.get('status','active')}', {parent_id})"
    )
    res = run_sql(sql)
    if "_err" in res:
        # Only print first few errors to keep output manageable
        if err < 5:
            print(f"  ✗ {path}: {res['_err'][:150]}")
        err += 1
    else:
        ok += 1
    if (i+1) % 30 == 0:
        print(f"  ... progress: {i+1}/{len(to_insert)} (ok={ok}, err={err})")

print(f"\n  Done: {ok} inserted, {err} errors")

# ============================================================
# Step 4: final state
# ============================================================
print(f"\n=== Final: mavis.summary ===")
res = run_sql("SELECT kind, category, status, count(*) AS n FROM mavis.items GROUP BY kind, category, status ORDER BY kind, category, status")
if isinstance(res, list):
    total = 0
    for r in res:
        total += r['n']
        print(f"  {r['kind']:7} {str(r.get('category') or '-'):12} {r['status']:10} : {r['n']:4}")
    print(f"  {'TOTAL':7} {'':12} {'':10} : {total:4}")

print(f"\n=== Final: mavis.tree (full, top 50) ===")
res = run_sql("SELECT depth, path_string, kind, category FROM mavis.tree ORDER BY depth, path_string LIMIT 60")
if isinstance(res, list):
    for r in res:
        prefix = "  " * r['depth']
        cat = r.get('category') or '-'
        print(f"  {prefix}{r['path_string']:50} {r['kind']:7} {cat}")
