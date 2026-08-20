#!/usr/bin/env python3
"""
mavis — Mavis CLI (Kilo Code-inspired, M3-native)

The Mavis M3 platform runs as a single root session, but it can be operated
locally as a CLI that exposes the same surface Kilo Code has. This is the
"real Jarvis" — not just talking, but the workflow routing.

Subcommands:
  mavis run [message]     one-shot LLM call (--mode or --agent=<name>)
  mavis serve              headless server (HTTP + SSE)
  mavis attach <url>       attach to a running mavis server
  mavis provider list      show all configured LLM providers
  mavis skills [query]     list/search the 85 skills
  mavis modes              list built-in modes
  mavis agents             list custom .md agents
  mavis team "goal"        run a swarm (Kimi K3-style)
  mavis mcp list           list MCP servers
  mavis session list       list active sessions
  mavis config             show mavis.json config
  mavis skills-rag         semantic skill search
"""
import argparse, json, os, re, sys, subprocess, urllib.request, urllib.error
from pathlib import Path

# ============================================================
# Configuration
# ============================================================
HOME = Path(os.environ.get('HOME', '/root'))
SUPABASE_KEY = os.environ.get('SUPABASEMGMT_API_KEY') or os.environ.get('MAVIS_TOKEN')
REF = 'tuwshovazpqzsvwnicgj'  # francis-production-core
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
SCRIPT_DIR = Path(os.path.realpath(__file__)).parent

# ============================================================
# Helpers
# ============================================================
def run_sql(sql, key=SUPABASE_KEY):
    """Run SQL on mavis.items via Supabase mgmt API."""
    r = subprocess.run([
      "curl", "-fsS", "--max-time", "30",
      "-X", "POST",
      f"https://api.supabase.com/v1/projects/{REF}/database/query",
      "-H", "Authorization: Bearer " + (key or ""),
      "-H", "Content-Type: application/json",
      "-d", json.dumps({"query": sql}),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        return {"_err": r.stderr[:300]}
    if not r.stdout.strip(): return []
    try: return json.loads(r.stdout)
    except: return {"_raw": r.stdout[:500]}

def call_llm(model, system, user, max_tokens=1500, temperature=0.3, api_key=None):
    """Call any LLM via OpenRouter."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "no API key (need OPENROUTER_API_KEY)"}
    payload = {
        "model": model, "max_tokens": max_tokens, "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # Stats tracking
    _stats = _Stats()
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mavis.local",
        "X-Title": "mavis-cli",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read().decode())
        usage = body.get("usage", {})
        _stats.log(model, usage)
        return {"ok": True, "text": body["choices"][0]["message"]["content"],
                "model": model, "usage": usage}
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode()[:300]
        except: pass
        return {"ok": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}

# ============================================================
# Built-in modes (Kilo-style: Code / Architect / Ask / Debug / Orchestrator)
# ============================================================
MODES = {
    "code": {
        "name": "Code",
        "description": "Write, edit, refactor code with full tool access",
        "system": "You are Mavis in Code mode. Write, edit, refactor code. Be terse, action-first. Show the code, not the lecture.",
    },
    "architect": {
        "name": "Architect",
        "description": "Plan systems, evaluate tradeoffs, design before code",
        "system": "You are Mavis in Architect mode. Focus on planning, tradeoffs, system design. Output decisions, not code.",
    },
    "ask": {
        "name": "Ask",
        "description": "Q&A mode, no tool calls, cite sources",
        "system": "You are Mavis in Ask mode. Answer questions concisely. Cite sources. No tool calls, no code edits.",
    },
    "debug": {
        "name": "Debug",
        "description": "Root cause analysis with logs, traces, tests",
        "system": "You are Mavis in Debug mode. Find root causes. Use logs, traces, tests. Verify before claiming fixed.",
    },
    "orchestrator": {
        "name": "Orchestrator",
        "description": "Dispatch to sub-agents, route work across the team (Kimi K3 swarm pattern)",
        "system": "You are Mavis in Orchestrator mode. Decompose the task, dispatch to sub-agents (MaxClaw/Hermes/Coder/Verifier), synthesize. Apply Kimi K3 swarm pattern. Show sub-tasks, evidence, confidence.",
    },
}

# ============================================================
# .md agent loader (Kilo .kilo/agents/<name>.md format)
# ============================================================
AGENTS_DIR = SCRIPT_DIR / "agents"

def load_md_agents():
    """Load all .md agents from agents/ dir. Format: YAML frontmatter + markdown body."""
    agents = {}
    if not AGENTS_DIR.exists():
        return agents
    for f in sorted(AGENTS_DIR.glob("*.md")):
        try:
            text = f.read_text()
            m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', text, re.DOTALL)
            if not m:
                print(f"warn: {f.name} has no frontmatter, skipping", file=sys.stderr)
                continue
            fm, body = m.group(1), m.group(2)
            meta = {}
            for line in fm.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")
            name = f.stem
            agents[name] = {
                'name': name,
                'description': meta.get('description', ''),
                'mode': meta.get('mode', 'subagent'),
                'model': meta.get('model', 'moonshotai/kimi-k3'),
                'temperature': float(meta.get('temperature', 0.3)),
                'display_name': meta.get('displayName', name),
                'color': meta.get('color', '#888'),
                'steps': int(meta.get('steps', 30)),
                'system': body.strip(),
                'source': str(f),
            }
        except Exception as e:
            print(f"warn: failed to load {f.name}: {e}", file=sys.stderr)
    return agents

MD_AGENTS = load_md_agents()

# ============================================================
# Stats logger (tracks every LLM call to ~/.mavis/stats.jsonl)
# ============================================================
STATS_DIR = Path(os.environ.get('HOME', '/root')) / '.mavis'
STATS_FILE = STATS_DIR / 'stats.jsonl'

class _Stats:
    def __init__(self):
        STATS_DIR.mkdir(parents=True, exist_ok=True)
    def log(self, model, usage):
        if not usage: return
        try:
            rec = {
                "ts": int(__import__('time').time()),
                "model": model,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "cost": usage.get("cost", 0.0),
            }
            with open(STATS_FILE, 'a') as f:
                f.write(json.dumps(rec) + '\n')
        except Exception as e:
            pass  # don't break the LLM call if stats fail
    def aggregate(self, since_ts=None):
        if not STATS_FILE.exists(): return None
        total = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0, "by_model": {}}
        try:
            for line in STATS_FILE.read_text().splitlines():
                if not line.strip(): continue
                rec = json.loads(line)
                if since_ts and rec.get("ts", 0) < since_ts: continue
                total["calls"] += 1
                total["prompt_tokens"] += rec.get("prompt_tokens", 0)
                total["completion_tokens"] += rec.get("completion_tokens", 0)
                total["total_tokens"] += rec.get("total_tokens", 0)
                total["cost"] += rec.get("cost", 0.0)
                m = rec.get("model", "?")
                bm = total["by_model"].setdefault(m, {"calls": 0, "tokens": 0, "cost": 0.0})
                bm["calls"] += 1
                bm["tokens"] += rec.get("total_tokens", 0)
                bm["cost"] += rec.get("cost", 0.0)
        except Exception as e:
            pass
        return total

# Initialize stats singleton
_Stats()

# ============================================================
# Subcommands
# ============================================================
def cmd_provider_list(args):
    """List all LLM providers available in the vault."""
    providers_map = {
        'anthropic': 'Anthropic', 'openai': 'OpenAI', 'openrouter': 'OpenRouter',
        'gemini': 'Google Gemini', 'deepseek': 'DeepSeek', 'grok': 'xAI (Grok)',
        'xai': 'xAI (Grok)', 'groq': 'Groq', 'mistral': 'Mistral', 'cohere': 'Cohere',
        'nvidia': 'NVIDIA NIM', 'nim': 'NVIDIA NIM', 'ollama': 'Ollama Cloud',
        'huggingface': 'HuggingFace', 'opencode': 'OpenCode', 'stitch': 'Stitch',
        'tavily': 'Tavily', 'warp': 'Warp2', 'brave': 'Brave', 'github': 'GitHub',
        'cf': 'Cloudflare', 'cloudflare': 'Cloudflare', 'supabase': 'Supabase Mgmt',
        'netlify': 'Netlify', 'r2': 'Cloudflare R2', 'tailscale': 'Tailscale',
        'telegram': 'Telegram', 'virustotal': 'VirusTotal', 'cursor': 'Cursor',
    }
    found = {}
    for k, v in sorted(os.environ.items()):
        if not v: continue
        if not any(s in k for s in ['API_KEY', 'TOKEN', 'AUTH']): continue
        if k.startswith('SUPABASE_') or 'PUBLIC' in k: continue
        lname = k.lower()
        prov = None
        for needle, name in providers_map.items():
            if needle in lname:
                prov = name; break
        if not prov: prov = k.replace('_API_KEY','').replace('_TOKEN','').replace('_AUTH','')
        if prov not in found:
            found[prov] = k
    print(f"\n{'Provider':<25} {'Env var':<40}")
    print("-" * 65)
    for prov, env in sorted(found.items()):
        print(f"  {prov:<23} {env}")
    print(f"\n{len(found)} unique providers configured\n")

def cmd_skills(args):
    """List or search the 85 skills (from mavis.items)."""
    q = (args.query or "").lower().strip() if hasattr(args, 'query') else ""
    res = run_sql("SELECT name, description FROM mavis.items WHERE category IN ('skill', 'capability') ORDER BY name")
    if not isinstance(res, list):
        print("ERROR:", res); return
    print(f"\n{'Skill':<35} {'When to use (from summary)':<60}")
    print("-" * 95)
    matches = 0
    for row in res:
        name = row.get('name', '')[:33]
        desc = (row.get('description') or '')[:60]
        if q and q not in (name + ' ' + desc).lower(): continue
        matches += 1
        print(f"  {name:<33} {desc}")
    if q:
        print(f"\n{matches} skills matching '{q}' (out of {len(res)})\n")
    else:
        print(f"\n{len(res)} skills + capabilities total\n")

def cmd_modes(args):
    """List available modes."""
    print(f"\n{'Mode':<14} {'Description':<70}")
    print("-" * 84)
    for k, m in MODES.items():
        print(f"  {k:<12} {m['description']}")
    print(f"\n{len(MODES)} modes. Use: mavis run --mode=code \"...\"")
    print("Or: mavis run --agent=<name> \"...\" (custom .md agents)\n")

def cmd_run(args):
    """One-shot LLM call in a given mode OR custom .md agent."""
    msg = ' '.join(args.message) if args.message else ""
    if not msg:
        print("ERROR: no message"); return
    mode = getattr(args, 'mode', 'orchestrator') or 'orchestrator'
    agent_name = getattr(args, 'agent', None)
    if agent_name:
        if agent_name not in MD_AGENTS:
            print(f"ERROR: unknown agent '{agent_name}'. Available: {', '.join(MD_AGENTS)}"); return
        a = MD_AGENTS[agent_name]
        system = a['system']
        model = getattr(args, 'model', None) or a['model']
        temperature = a['temperature']
        print(f"mavis run [agent:{agent_name}] model={model}\n> {msg}\n")
    else:
        if mode not in MODES:
            print(f"ERROR: unknown mode '{mode}'. Available: {', '.join(MODES)}"); return
        system = MODES[mode]['system']
        model = getattr(args, 'model', None) or 'moonshotai/kimi-k3'
        temperature = 0.3
        print(f"mavis run [{mode}] model={model}\n> {msg}\n")
    r = call_llm(model, system, msg, temperature=temperature)
    if r['ok']:
        print(r['text'])
        if r.get('usage'):
            u = r['usage']
            print(f"\n[usage: prompt={u.get('prompt_tokens','?')} completion={u.get('completion_tokens','?')} cost=${u.get('cost','?')}]")
    else:
        print(f"ERROR: {r.get('error','?')}, trying llama fallback...")
        r2 = call_llm("meta-llama/llama-3.1-70b-instruct", system, msg, temperature=temperature)
        if r2['ok']:
            print(r2['text'])
            if r2.get('usage'):
                u = r2['usage']
                print(f"\n[usage: prompt={u.get('prompt_tokens','?')} completion={u.get('completion_tokens','?')} cost=${u.get('cost','?')}]")
        else:
            print(f"FALLBACK ALSO FAILED: {r2.get('error','?')}")

def cmd_skills_rag(args):
    """Semantic search over skills (uses skill_matcher.py)."""
    q = ' '.join(args.query) if args.query else ""
    if not q:
        print("Usage: mavis skills-rag <query>"); return
    here = Path('/usr/local/share/mavis/skill_matcher.py')
    if not here.exists():
        here = SCRIPT_DIR.parent / "mavis-skills" / "skill_matcher.py"
    if here.exists():
        r = subprocess.run(["python3", str(here), q, "--json"], capture_output=True, text=True)
        if r.returncode == 0:
            try:
                d = json.loads(r.stdout)
            except:
                print(r.stdout[:500]); return
            print(f"\nTop skills for: \"{q}\"\n")
            for i, m in enumerate(d.get('matched', []), 1):
                print(f"{i}. {m['name']}  (score={m['score']})")
                print(f"   WHY: {m.get('rationale', '')}")
                if m.get('deliverable'):
                    print(f"   DELIVERS: {m['deliverable'][:100]}")
                print()
        else:
            print(f"ERROR: {r.stderr[:300]}")
    else:
        print(f"ERROR: skill_matcher.py not found")

def cmd_serve(args):
    """Headless server: accept HTTP requests, dispatch to LLM."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    port = args.port or 7741
    model = args.model or 'moonshotai/kimi-k3'
    mode = args.mode or 'orchestrator'
    print(f"mavis serve on :{port}  mode={mode}  model={model}")
    print("Endpoints:")
    print(f"  POST /run        body: {{\"message\":\"...\", \"mode\":\"code\", \"agent\":\"swarm-orchestrator\"}}")
    print(f"  GET  /health     returns status")
    print(f"  GET  /skills     returns all skills")
    print(f"  GET  /agents     returns .md agents")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a, **k): pass
        def do_GET(self):
            if self.path == '/health':
                self._json({"ok": True, "model": model, "mode": mode, "agents": list(MD_AGENTS.keys()), "modes": list(MODES.keys())})
            elif self.path == '/skills':
                res = run_sql("SELECT name, description FROM mavis.items WHERE category IN ('skill','capability') ORDER BY name")
                self._json({"skills": res if isinstance(res, list) else []})
            elif self.path == '/agents':
                self._json({"agents": [{"name": a['name'], "description": a['description'], "model": a['model'], "mode": a['mode']} for a in MD_AGENTS.values()]})
            else:
                self._json({"error": "not found"}, 404)
        def do_POST(self):
            if self.path == '/run':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length).decode()) if length else {}
                    msg = body.get('message', '')
                    m = body.get('mode', mode)
                    agent_name = body.get('agent')
                    if agent_name and agent_name in MD_AGENTS:
                        a = MD_AGENTS[agent_name]
                        system = a['system']; m_model = a['model']; temperature = a['temperature']
                    elif m in MODES:
                        system = MODES[m]['system']; m_model = body.get('model', model); temperature = 0.3
                    else:
                        self._json({"error": f"unknown mode: {m} or agent: {agent_name}"}, 400); return
                    if not msg:
                        self._json({"error": "no message"}, 400); return
                    r = call_llm(m_model, system, msg, temperature=temperature)
                    if r['ok']:
                        self._json({"ok": True, "text": r['text'], "model": m_model, "usage": r.get('usage', {})})
                    else:
                        if 'kimi' in m_model.lower() or 'k3' in m_model.lower():
                            r2 = call_llm("meta-llama/llama-3.1-70b-instruct", system, msg, temperature=temperature)
                            if r2['ok']:
                                self._json({"ok": True, "text": r2['text'], "model": "meta-llama/llama-3.1-70b-instruct", "fallback": True, "usage": r2.get('usage', {})}); return
                        self._json({"ok": False, "error": r.get('error', '?')}, 500)
                except Exception as e:
                    self._json({"ok": False, "error": f"server: {str(e)[:200]}"}, 500)
            else:
                self._json({"error": "not found"}, 404)
        def _json(self, obj, code=200):
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(obj, ensure_ascii=False).encode())
    s = HTTPServer(('0.0.0.0', port), Handler)
    print(f"  Listening on http://0.0.0.0:{port}")
    try: s.serve_forever()
    except KeyboardInterrupt: print("\n  Stopped.")

def cmd_mcp(args):
    """List MCP servers (from mavis.json config)."""
    cfg_path = SCRIPT_DIR / "config" / "mavis.json"
    if not cfg_path.exists():
        print("ERROR: config/mavis.json not found"); return
    cfg = json.loads(cfg_path.read_text())
    mcp = cfg.get('mcp', {})
    print(f"\n{'MCP':<20} {'Type':<10} {'Details'}")
    print("-" * 75)
    for k, v in mcp.items():
        if v.get('type') == 'remote':
            d = v.get('url', '?')[:50]
        else:
            d = ' '.join(v.get('command', []))[:50]
        print(f"  {k:<18} {v.get('type','?'):<10} {d}")
    print(f"\n{len(mcp)} MCP servers in mavis.json\n")
    print("To add: edit mavis.json, or run: kilo mcp add <name> (via @kilocode/cli)\n")

def cmd_agent_list(args):
    """List .md agents loaded from agents/ (Kilo .kilo/agents/<name>.md format)."""
    if not MD_AGENTS:
        print(f"\nNo .md agents loaded. Add .md files to {AGENTS_DIR}\n")
        return
    print(f"\n{'Agent':<28} {'Mode':<10} {'Model':<40} {'Description'}")
    print("-" * 130)
    for name, a in MD_AGENTS.items():
        print(f"  {a['display_name']:<26} {a['mode']:<10} {a['model']:<40} {a['description'][:60]}")
    print(f"\n{len(MD_AGENTS)} .md agents loaded from {AGENTS_DIR}")
    print("Run: mavis run --agent=<name> '<message>'\n")

def cmd_session_list(args):
    """List active sessions (delegates to mavis tool)."""
    r = subprocess.run(["mavis", "session", "list", "limit=10"], capture_output=True, text=True,
                       env={**os.environ, 'PATH': '/usr/local/bin:' + os.environ.get('PATH','')})
    if r.returncode == 0:
        try:
            d = json.loads(r.stdout)
            for s in d.get('sessions', [])[:20]:
                print(f"  {s.get('session_id','')[:14]:<15} {s.get('agent_name',''):<10} {s.get('title','')[:60]}")
        except:
            print(r.stdout[:500])
    else:
        print(r.stderr[:300])

def cmd_team(args):
    """Run a swarm (delegates to mavis-swarm or mavis-swarm-llm)."""
    goal = ' '.join(args.goal) if args.goal else ""
    n = args.workers or 5
    real = getattr(args, 'real', False)
    model = getattr(args, 'model', 'moonshotai/kimi-k3') or 'moonshotai/kimi-k3'
    if not goal:
        print("Usage: mavis team \"<goal>\" [--real] [--model=<m>] [--workers N]"); return
    if real:
        r = subprocess.run(["mavis-swarm-llm", goal, "--workers", str(n), "--model", model], capture_output=True, text=True, timeout=300)
    else:
        r = subprocess.run(["mavis-swarm", goal, "--workers", str(n)], capture_output=True, text=True, timeout=120)
    print(r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout)
    if r.returncode != 0: print(f"ERR: {r.stderr[:300]}")

def cmd_config_show(args):
    """Show mavis.json config (kilo.json-inspired)."""
    cfg_path = SCRIPT_DIR / "config" / "mavis.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found"); return
    cfg = json.loads(cfg_path.read_text())
    print(f"\n=== Mavis config ({cfg.get('version','?')}) ===")
    print(f"Default model: {cfg.get('model','?')}")
    print(f"Default agent: {cfg.get('default_agent','?')}")
    print(f"\nProviders ({len(cfg.get('provider',{}))}):")
    for k, v in cfg.get('provider', {}).items():
        envs = ', '.join(v.get('env', []))
        print(f"  {k:<15} env=[{envs}]")
    print(f"\nAgents ({len(cfg.get('agent',{}))}):")
    for k, v in cfg.get('agent', {}).items():
        m = v.get('model', '?')
        print(f"  {k:<14} model={m:<35} steps={v.get('steps','?')}")
    print(f"\nMCP servers ({len(cfg.get('mcp',{}))}):")
    for k, v in cfg.get('mcp', {}).items():
        print(f"  {k:<15} type={v.get('type','?')}")
    print(f"\nMavis section: {json.dumps(cfg.get('mavis',{}), indent=2)}\n")

def cmd_config_get(args):
    """Get a config key (dotted path like 'provider.openrouter.options.baseURL')."""
    cfg_path = SCRIPT_DIR / "config" / "mavis.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found"); return
    cfg = json.loads(cfg_path.read_text())
    path = args.key
    cur = cfg
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            print(f"ERROR: key '{path}' not found (failed at '{part}')"); return
    print(json.dumps(cur, indent=2))

def cmd_config_set(args):
    """Set a config key. Usage: mavis config set <key> <json-value>"""
    cfg_path = SCRIPT_DIR / "config" / "mavis.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found"); return
    cfg = json.loads(cfg_path.read_text())
    path = args.key
    # Parse value as JSON
    try:
        val = json.loads(args.value)
    except json.JSONDecodeError:
        val = args.value  # fallback to string
    # Traverse path
    parts = path.split('.')
    cur = cfg
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = val
    # Backup + write
    bak = cfg_path.with_suffix('.json.bak')
    bak.write_text(cfg_path.read_text())
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print(f"✅ Set {path} = {json.dumps(val)}")
    print(f"   Backup: {bak}")

def cmd_models(args):
    """List models from mavis.json. Optionally filter by provider."""
    cfg_path = SCRIPT_DIR / "config" / "mavis.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found"); return
    cfg = json.loads(cfg_path.read_text())
    providers = cfg.get('provider', {})
    provider_filter = getattr(args, 'provider', None)
    total = 0
    print(f"\n{'Provider':<14} {'Model ID':<45} {'Display name':<30} {'Context'}")
    print("-" * 100)
    for prov_id, prov in sorted(providers.items()):
        if provider_filter and prov_id != provider_filter: continue
        models = prov.get('models', {})
        if not models:
            print(f"  {prov_id:<12} (no models in config — uses provider's default list)")
            continue
        for mid, m in sorted(models.items()):
            ctx = m.get('context', '?')
            name = m.get('name', mid)
            print(f"  {prov_id:<12} {mid:<43} {name:<30} {ctx}")
            total += 1
    print(f"\n{total} models in mavis.json")
    if not provider_filter:
        print("Filter by provider: mavis models openrouter\n")

def cmd_stats(args):
    """Show aggregate token usage and cost from ~/.mavis/stats.jsonl."""
    if not STATS_FILE.exists():
        print(f"\nNo stats yet. Run a few `mavis run` calls first.\n")
        print(f"Stats file: {STATS_FILE}\n")
        return
    s = _Stats().aggregate()
    if not s or s["calls"] == 0:
        print(f"\nNo calls logged yet.\n"); return
    print(f"\n=== Mavis stats ({s['calls']} LLM calls) ===")
    print(f"Total tokens:  {s['total_tokens']:>12,}")
    print(f"  Prompt:      {s['prompt_tokens']:>12,}")
    print(f"  Completion:  {s['completion_tokens']:>12,}")
    print(f"Total cost:    ${s['cost']:.4f}")
    print(f"\nBy model:")
    print(f"  {'Model':<45} {'Calls':>6} {'Tokens':>10} {'Cost':>10}")
    print("  " + "-" * 71)
    for m, bm in sorted(s["by_model"].items(), key=lambda x: -x[1]["cost"]):
        print(f"  {m:<45} {bm['calls']:>6} {bm['tokens']:>10,} ${bm['cost']:>9.4f}")
    print(f"\nStats file: {STATS_FILE}\n")

def cmd_attach(args):
    """Connect to a running mavis serve. Interactive REPL."""
    import urllib.request
    url = args.url.rstrip('/')
    print(f"mavis attach {url}")
    print("Type 'help' for commands, 'quit' to exit.\n")
    while True:
        try:
            line = input("mavis> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not line: continue
        if line in ('quit', 'exit', 'q'):
            break
        if line == 'help':
            print("  /health      GET /health")
            print("  /skills      GET /skills (count)")
            print("  /agents      GET /agents (list)")
            print("  <message>    POST /run with <message> in default mode")
            print("  /mode=X      change default mode (code/architect/ask/debug/orchestrator)")
            print("  /agent=X     change default agent (custom .md)")
            print("  quit         exit")
            continue
        cur_mode = 'orchestrator'
        cur_agent = None
        if line.startswith('/health'):
            try:
                r = urllib.request.urlopen(url + '/health', timeout=10)
                print(r.read().decode()[:500])
            except Exception as e:
                print(f"ERROR: {e}")
        elif line.startswith('/skills'):
            try:
                r = urllib.request.urlopen(url + '/skills', timeout=10)
                d = json.loads(r.read().decode())
                print(f"{len(d.get('skills',[]))} skills")
            except Exception as e:
                print(f"ERROR: {e}")
        elif line.startswith('/agents'):
            try:
                r = urllib.request.urlopen(url + '/agents', timeout=10)
                d = json.loads(r.read().decode())
                for a in d.get('agents', []):
                    print(f"  {a['name']:<28} {a.get('description','')[:60]}")
            except Exception as e:
                print(f"ERROR: {e}")
        elif line.startswith('/mode='):
            cur_mode = line.split('=',1)[1]
            print(f"  mode = {cur_mode}")
        elif line.startswith('/agent='):
            cur_agent = line.split('=',1)[1]
            print(f"  agent = {cur_agent}")
        else:
            # POST /run
            body = json.dumps({"message": line, "mode": cur_mode, "agent": cur_agent}).encode()
            req = urllib.request.Request(url + '/run', data=body, headers={'Content-Type': 'application/json'}, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    d = json.loads(r.read().decode())
                if d.get('ok'):
                    print(d.get('text', ''))
                    if d.get('usage'):
                        u = d['usage']
                        print(f"\n[usage: prompt={u.get('prompt_tokens','?')} completion={u.get('completion_tokens','?')} cost=${u.get('cost','?')}]")
                else:
                    print(f"ERROR: {d.get('error','?')}")
            except Exception as e:
                print(f"ERROR: {e}")
    print("Disconnected.")

# ============================================================
# CLI parser
# ============================================================
def main():
    p = argparse.ArgumentParser(
        prog="mavis",
        description="Mavis CLI — Kilo Code-style workflow router for M3",
        epilog="""Examples:
  mavis run "Explain the OAuth pool unlock"
  mavis run --mode=code "Refactor this Python function"
  mavis run --agent=swarm-orchestrator "Plan a refactor of X"
  mavis provider list
  mavis skills "swarm"
  mavis modes
  mavis team "Compare 5 vector databases"
  mavis serve --port 7741

See also: mavis-swarm, mavis-swarm-llm (in /usr/local/bin/).
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd')

    s = sub.add_parser('provider', help='List LLM providers')
    s.add_argument('action', nargs='?', default='list')
    sp = sub.add_parser('skills', help='List or search skills (85 total)')
    sp.add_argument('query', nargs='?', help='Search query (optional)')
    sub.add_parser('modes', help='List built-in modes')
    sr = sub.add_parser('run', help='One-shot LLM call')
    sr.add_argument('message', nargs='+', help='Message to send')
    sr.add_argument('--mode', '-m', default='orchestrator', help='Mode (default: orchestrator)')
    sr.add_argument('--model', default='moonshotai/kimi-k3', help='Model ID')
    sr.add_argument('--agent', '-a', help='Use a custom .md agent (name without .md)')
    ssr = sub.add_parser('skills-rag', help='Semantic skill search')
    ssr.add_argument('query', nargs='+')
    ss = sub.add_parser('serve', help='Start headless HTTP server')
    ss.add_argument('--port', '-p', type=int, default=7741)
    ss.add_argument('--model', default='moonshotai/kimi-k3')
    ss.add_argument('--mode', default='orchestrator')
    sub.add_parser('mcp', help='List/manage MCP servers')
    sub.add_parser('agents', help='List .md custom agents (Kilo format)')
    sub.add_parser('session', help='List active sessions')
    st = sub.add_parser('team', help='Run a swarm (Kimi K3-style)')
    st.add_argument('goal', nargs='+', help='Swarm goal')
    st.add_argument('--workers', '-n', type=int, default=5)
    st.add_argument('--real', action='store_true', help='Use real LLM workers (costs API credits)')
    st.add_argument('--model', default='moonshotai/kimi-k3', help='Model for real workers')
    sc = sub.add_parser('config', help='Show or edit mavis.json config')
    sc.add_argument('action', nargs='?', default='show', help='show | get | set')
    sc.add_argument('key', nargs='?', help='Config key (dotted path, for get/set)')
    sc.add_argument('value', nargs='?', help='JSON value (for set)')
    sm = sub.add_parser('models', help='List available models from mavis.json')
    sm.add_argument('provider', nargs='?', help='Filter by provider ID (e.g. openrouter)')
    sub.add_parser('stats', help='Aggregate token usage + cost from stats.jsonl')
    sat = sub.add_parser('attach', help='Connect to a running mavis serve (REPL)')
    sat.add_argument('url', help='URL of the mavis server (e.g. http://localhost:7741)')

    args = p.parse_args()
    if not args.cmd:
        p.print_help(); return
    # Sub-action dispatch for config
    if args.cmd == 'config':
        action = getattr(args, 'action', 'show') or 'show'
        if action == 'show': cmd_config_show(args)
        elif action == 'get': cmd_config_get(args)
        elif action == 'set': cmd_config_set(args)
        else: print(f"ERROR: unknown config action '{action}'. Use: show | get | set")
        return
    dispatch = {
        'provider': cmd_provider_list, 'skills': cmd_skills, 'modes': cmd_modes,
        'run': cmd_run, 'skills-rag': cmd_skills_rag, 'serve': cmd_serve,
        'mcp': cmd_mcp, 'agents': cmd_agent_list, 'session': cmd_session_list,
        'team': cmd_team, 'models': cmd_models, 'stats': cmd_stats, 'attach': cmd_attach,
    }
    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
