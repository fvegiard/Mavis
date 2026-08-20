#!/usr/bin/env python3
"""
Mavis: add /Mavis/env/hosts folder with Mac Mini (MX Linux) + fv-legion-2 entries.
This is a small, targeted insert — not the full ingest resume.
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
            if not r.stdout.strip():
                return {"_ok": True}
            try: return json.loads(r.stdout)
            except: return {"_raw": r.stdout[:500]}
        if "429" in r.stderr or "rate" in r.stderr.lower():
            wait = backoff * (2 ** attempt)
            print(f"  [429] backing off {wait}s...", flush=True)
            time.sleep(wait)
            continue
        return {"_err": r.stderr[:500]}
    return {"_err": "max retries (429)"}

# 1) get parent folder id for env (one query, no nesting)
res = run_sql("""SELECT e.id AS env_id,
  (SELECT id FROM mavis.items WHERE name='hosts' AND parent_id=e.id) AS hosts_id
  FROM mavis.items e WHERE e.name='env' AND e.parent_id=(SELECT id FROM mavis.items WHERE name='Mavis' AND parent_id IS NULL)""")
if not isinstance(res, list) or not res:
    print("FAIL: env folder not found", res); sys.exit(1)
env_id = res[0]["env_id"]
hosts_id = res[0].get("hosts_id")
print(f"env folder id: {env_id}, hosts folder id: {hosts_id}")
hosts_exists = isinstance(res, list) and len(res) > 0
print(f"hosts folder exists: {hosts_exists}")

# 3) create hosts folder if needed
if not hosts_id:
    sql = f"""INSERT INTO mavis.items (kind, name, title, description, payload, source, status, parent_id)
VALUES ('folder', 'hosts', 'Hosts — Francis''s machines', 'Physical/virtual machines Francis owns. Reachable via Tailscale. Note OS, role, current status.',
'{{"vpn": "tailscale", "auth": "TAILSCALE_AUTHKEY env (expires 2026-09-25)"}}'::jsonb,
'self_inventory', 'active', {env_id}) RETURNING id"""
    res = run_sql(sql)
    if not isinstance(res, list) or not res:
        print("FAIL create hosts folder:", res); sys.exit(1)
    hosts_id = res[0]["id"]
    print(f"✓ Created /Mavis/env/hosts id={hosts_id}")
else:
    hosts_id = res[0]["id"]
    print(f"Reusing /Mavis/env/hosts id={hosts_id}")

# 4) insert host entries
HOSTS = [
  {"name": "mac_mini", "title": "Mac Mini (MX Linux)",
   "description": "Small form-factor desktop. Runs MX Linux (Debian-based, NOT macOS). Primary always-on deploy host. Reachable via Tailscale. Use apt/bash/systemd.",
   "payload": {"os": "MX Linux", "os_family": "debian", "form_factor": "mini PC", "pkg_mgr": "apt", "shell": "bash", "service_mgr": "systemd", "tailscale": "yes", "role": "primary_deploy_host", "reachable_via": "tailscale_ssh", "note": "Always refer to it as 'Mac Mini (MX Linux)'. The 'mini' is the form factor, not the OS."},
   "triggers": ["mac mini", "mini", "mxlinux", "mx linux", "deploy host"]},
  {"name": "fv_legion_2", "title": "fv-legion-2 (Lenovo)",
   "description": "Lenovo workstation, Tailscale 100.102.60.77. OFFLINE since 2026-07-26. WOL blocked. To wake: Tailscale admin Wake button or physical power-on.",
   "payload": {"vendor": "Lenovo", "tailscale_ip": "100.102.60.77", "status": "offline", "offline_since": "2026-07-26", "wake_method": "tailscale_admin_wake_button", "note": "Auth key expires 2026-09-25 (rotation cron exists)"},
   "status": "inactive",
   "triggers": ["fv-legion-2", "legion", "lenovo", "wake", "wol"]},
  {"name": "mavis_sandbox", "title": "Mavis Sandbox (this host)",
   "description": "Cloud sandbox where Mavis (M3) runs. Linux, no systemd, no Docker. Used for Mavis's own work. Not reachable from outside.",
   "payload": {"os": "linux", "os_family": "debian (container)", "pkg_mgr": "apt (sparse)", "shell": "bash", "service_mgr": "none (no systemd)", "tailscale": "no", "role": "mavis_runtime", "workspace": "/workspace", "note": "Where I (Mavis) am. Tailscale binary installed but daemon cannot run."},
   "triggers": ["sandbox", "this host", "mavis runtime", "where am i"]},
]

for h in HOSTS:
    name = h["name"].replace("'", "''")
    desc = h["description"].replace("'", "''")
    title = h["title"].replace("'", "''")
    payload = json.dumps(h["payload"]).replace("'", "''")
    triggers_arr = "{" + ",".join('"' + t.replace('"', '\\"') + '"' for t in h.get("triggers", [])) + "}"
    status = h.get("status", "active")
    # Check if already exists
    check = run_sql(f"SELECT id FROM mavis.items WHERE name='{name}' AND parent_id={hosts_id}")
    if isinstance(check, list) and check:
        print(f"  ↻ {name} already exists (id={check[0]['id']}), skipping")
        continue
    sql = (
        f"INSERT INTO mavis.items (kind, category, name, title, description, triggers, payload, source, status, parent_id) "
        f"VALUES ('file', 'env', '{name}', '{title}', '{desc}', '{triggers_arr}'::text[], "
        f"'{payload}'::jsonb, 'self_inventory', '{status}', {hosts_id})"
    )
    res = run_sql(sql)
    if "_err" in res:
        print(f"  ✗ {name}: {res['_err'][:200]}")
    else:
        print(f"  ✓ {name}")
    time.sleep(0.5)  # rate limit spacing

# 5) Final state
print("\n=== Final hosts state ===")
res = run_sql("SELECT name, title, status, payload FROM mavis.items WHERE parent_id=" + str(hosts_id) + " ORDER BY name")
if isinstance(res, list):
    for r in res:
        p = r.get('payload', {})
        print(f"  {r['name']:15} {r['title']:35} [{r['status']}] os={p.get('os', p.get('os_family','?'))}")
