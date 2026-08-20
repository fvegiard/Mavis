#!/usr/bin/env python3
"""
Mavis data ingestion — push 03_ingest.json into mavis.items.

Two-pass strategy:
  Pass 1: Insert all folders (no parent), capture id <-> path mapping
  Pass 2: Insert all files with parent_id resolved
"""
import json, subprocess, sys
from pathlib import Path

DATA = json.load(open('/workspace/mavis-ingest/03_ingest.json'))
SUPABASE_KEY = open('/tmp/_key').read().strip() if Path('/tmp/_key').exists() else None
# We'll inject the key at runtime via env
import os
SUPABASE_KEY = os.environ['SUPABASEMGMT_API_KEY']
REF = 'tuwshovazpqzsvwnicgj'

def run_sql(sql: str) -> dict:
    """Execute SQL via Supabase mgmt API, return parsed result."""
    import json as j
    r = subprocess.run([
      "curl", "-fsS", "--max-time", "60",
      "-X", "POST",
      f"https://api.supabase.com/v1/projects/{REF}/database/query",
      "-H", "Authorization: Bearer " + SUPABASE_KEY,
      "-H", "Content-Type: application/json",
      "-d", j.dumps({"query": sql}),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  SQL FAIL: {r.stderr[:500]}", file=sys.stderr)
        return {"_err": r.stderr[:500]}
    if not r.stdout.strip():
        return {"_ok": True, "_empty": True}
    try:
        return j.loads(r.stdout)
    except Exception:
        return {"_raw": r.stdout[:500]}

# ============================================================
# Pass 1: insert folders, build path -> id map
# ============================================================
folders = [it for it in DATA if it["kind"] == "folder"]
files   = [it for it in DATA if it["kind"] == "file"]

# Build parent path for each
def path_of(item):
    if item["parent"] is None:
        return item["name"]
    return item["parent"] + "/" + item["name"]

# Map for resolved parent_id
path_to_id = {}

print(f"=== Pass 1: insert {len(folders)} folders ===")
# Sort: parents before children. Folders with no parent first, then by depth.
def depth(p): return p.count("/")
folders.sort(key=lambda f: depth(path_of(f)))

for f in folders:
    path = path_of(f)
    # Resolve parent_id
    parent_id = "NULL"
    if f["parent"]:
        parent_path = f["parent"]
        if parent_path not in path_to_id:
            print(f"  ! FOLDER parent missing: {path} (parent={parent_path})")
            continue
        parent_id = str(path_to_id[parent_path])
    payload_json = json.dumps(f.get("payload", {})).replace("'", "''")
    desc = (f.get("description") or "").replace("'", "''")
    title = (f.get("title") or f["name"]).replace("'", "''")
    name = f["name"].replace("'", "''")
    sql = (
        f"INSERT INTO mavis.items (kind, name, title, description, payload, source, status, parent_id) "
        f"VALUES ('folder', '{name}', '{title}', '{desc}', '{payload_json}'::jsonb, "
        f"'{f.get('source','self_inventory')}', '{f.get('status','active')}', {parent_id}) "
        f"RETURNING id"
    )
    res = run_sql(sql)
    if "_err" in res or "id" not in (res[0] if isinstance(res, list) else {}):
        print(f"  ✗ {path}: {res}")
        continue
    new_id = res[0]["id"]
    path_to_id[path] = new_id
    print(f"  ✓ {path:50} → id={new_id}")

print(f"\nInserted {len(path_to_id)} folders, {len(folders) - len(path_to_id)} failed")

# ============================================================
# Pass 2: insert files
# ============================================================
print(f"\n=== Pass 2: insert {len(files)} files ===")
ok = 0
err = 0
for f in files:
    path = path_of(f)
    parent_path = f["parent"]
    if parent_path not in path_to_id:
        print(f"  ! FILE parent missing: {path}")
        err += 1
        continue
    parent_id = path_to_id[parent_path]
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
        print(f"  ✗ {path}: {res['_err'][:200]}")
        err += 1
    else:
        ok += 1

print(f"\n=== Done: {ok} files OK, {err} errors ===")

# ============================================================
# Verify
# ============================================================
print(f"\n=== Verify: mavis.summary ===")
res = run_sql("SELECT kind, category, status, count(*) AS n FROM mavis.items GROUP BY kind, category, status ORDER BY kind, category, status")
if isinstance(res, list):
    for r in res:
        print(f"  {r}")
else:
    print(res)

print(f"\n=== Verify: mavis.tree (first 30 rows) ===")
res = run_sql("SELECT depth, path_string, kind, category FROM mavis.tree ORDER BY depth, path_string LIMIT 30")
if isinstance(res, list):
    for r in res:
        print(f"  {'  '*r['depth']}{r['path_string']:50} {r['kind']:7} {r.get('category') or ''}")
