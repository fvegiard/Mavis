#!/usr/bin/env python3
"""
Mavis data ingestion — RESUME v2 with rate-limit handling.
- Reads current state of mavis.items
- Skips existing, inserts only missing
- Sleeps 5s between requests
- Retries on 429 with exponential backoff
"""
import json, subprocess, os, time, sys
from pathlib import Path

DATA = json.load(open('/workspace/mavis-ingest/03_ingest.json'))
KEY = os.environ['SUPABASEMGMT_API_KEY']
REF = 'tuwshovazpqzsvwnicgj'

# New additions (same as 05_resume.py)
VM_ADDS = []
# Load VM adds from 05_resume.py by importing the module
import importlib.util
spec = importlib.util.spec_from_file_location("resume_orig", "/workspace/mavis-ingest/05_resume.py")
mod = importlib.util.module_from_spec(spec)
# Don't execute, just read
with open('/workspace/mavis-ingest/05_resume.py') as f:
    content = f.read()
# Extract VM_ADDS list
import re
m = re.search(r'VM_ADDS = (\[.*?^\])', content, re.DOTALL | re.MULTILINE)
if m:
    VM_ADDS = eval(m.group(1))
print(f"VM_ADDS: {len(VM_ADDS)} items")

def run_sql(sql, max_retries=5):
    """Run SQL with retry on 429."""
    for attempt in range(max_retries):
        r = subprocess.run([
            "curl", "-sS", "--max-time", "30",
            "-w", "\n--HTTP %{http_code}",
            "-X", "POST",
            f"https://api.supabase.com/v1/projects/{REF}/database/query",
            "-H", "Authorization: Bearer " + KEY,
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"query": sql}),
        ], capture_output=True, text=True)
        if r.returncode != 0:
            return {"err": r.stderr[:200], "stdout": ""}
        if r.stdout:
            parts = r.stdout.rsplit('--HTTP ', 1)
            if len(parts) == 2:
                code = int(parts[1].strip())
                body = parts[0]
                if code == 429:
                    wait = 10 * (2 ** attempt)
                    print(f"  429 → wait {wait}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                    continue
                if code in (200, 201):
                    return {"ok": True, "body": body, "code": code}
                return {"err": f"HTTP {code}: {body[:200]}", "code": code}
    return {"err": "max retries exceeded", "code": 429}

# Step 1: read current state
print("=== Step 1: read current state ===")
r = run_sql("SELECT name, kind FROM mavis.items")
if r.get('err'):
    print(f"ERROR: {r['err']}"); sys.exit(1)
items = json.loads(r['body'])
existing = {it['name'] for it in items}
print(f"  Existing items: {len(items)}, unique names: {len(existing)}")

# Step 2: build all items to insert (data + VM_ADDS)
all_items = DATA.get('items', DATA) if isinstance(DATA, dict) else DATA
if VM_ADDS:
    all_items = list(all_items) + VM_ADDS
print(f"  Total to consider: {len(all_items)}")

# Step 3: filter to missing
missing = [it for it in all_items if it.get('name') not in existing]
print(f"  Missing: {len(missing)}")

# Step 4: build parent path → id map
parent_map = {it['name']: it.get('id') for it in items if it.get('kind') == 'folder'}

# Step 5: insert missing in order (folders first, then files)
folders = [it for it in missing if it.get('kind') == 'folder']
files = [it for it in missing if it.get('kind') != 'folder']
print(f"  Folders to insert: {len(folders)}")
print(f"  Files to insert: {len(files)}")

ok, err = 0, 0
for it in folders + files:
    name = it.get('name', '?')
    parent_name = it.get('parent', '')
    parent_id = parent_map.get(parent_name.split('/')[-1] if parent_name else '', '')
    if not parent_id and parent_name:
        # Try to find by full path
        for n, i in parent_map.items():
            if parent_name.endswith(n):
                parent_id = i; break
    if not parent_id:
        # Try by exact name
        for n, i in parent_map.items():
            if n == parent_name:
                parent_id = i; break
    # Build SQL
    title = it.get('title', name).replace("'", "''")
    desc = it.get('description', '').replace("'", "''")
    cat = it.get('category', '')
    payload = json.dumps(it.get('payload', {}))
    sql = f"""INSERT INTO mavis.items (kind, category, name, title, description, payload, parent_id)
VALUES ('{it.get('kind','file')}', '{cat}', '{name}', '{title}', '{desc}', '{payload.replace(chr(39), chr(39)+chr(39))}'::jsonb,
        {'NULL' if not parent_id else str(parent_id)});"""
    r = run_sql(sql)
    if r.get('ok'):
        ok += 1
        # Update parent_map if this was a folder
        if it.get('kind') == 'folder':
            # Get the new id (we need to query it)
            time.sleep(0.2)  # be gentle
            r2 = run_sql(f"SELECT id FROM mavis.items WHERE name = '{name}' AND kind = 'folder'")
            if r2.get('ok') and r2['body'].strip().startswith('['):
                arr = json.loads(r2['body'])
                if arr: parent_map[name] = arr[0]['id']
    else:
        err += 1
        if err < 5:
            print(f"  ✗ {name}: {r.get('err','?')[:200]}")
    # Be gentle: small sleep between every call
    time.sleep(0.5)
    if (ok + err) % 20 == 0:
        print(f"  Progress: {ok+err}/{len(folders)+len(files)} (ok={ok}, err={err})")

print(f"\n=== Done: {ok} inserted, {err} errors ===")
