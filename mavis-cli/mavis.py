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
        return {"ok": True, "text": body["choices"][0]["message"]["content"],
                "model": model, "usage": body.get("usage", {})}
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
    sub.add_parser('config', help='Show mavis.json config')

    args = p.parse_args()
    if not args.cmd:
        p.print_help(); return
    dispatch = {
        'provider': cmd_provider_list, 'skills': cmd_skills, 'modes': cmd_modes,
        'run': cmd_run, 'skills-rag': cmd_skills_rag, 'serve': cmd_serve,
        'mcp': cmd_mcp, 'agents': cmd_agent_list, 'session': cmd_session_list,
        'team': cmd_team, 'config': cmd_config_show,
    }
    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
