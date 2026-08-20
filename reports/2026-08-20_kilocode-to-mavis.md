# Kilo Code → Mavis Mapping (2026-08-20)

**Goal:** Make Mavis a "real Jarvis" by adopting Kilo Code's architecture for workflow routing, modes, providers, MCP, and skills. This report maps every Kilo Code concept to its Mavis equivalent, with implementation status.

---

## 1. TL;DR — what's already done

| Kilo Code feature | Mavis equivalent | Status |
|------------------|------------------|--------|
| `kilo` CLI (Kilo Code-style) | `mavis` Python CLI (11 subcommands) | ✅ DONE this session |
| `kilo.json` config | `mavis.json` (7 providers, 5 agents, 3 MCP) | ✅ DONE this session |
| `.kilo/agents/<name>.md` (custom agents) | `mavis-cli/agents/*.md` (3 agents) | ✅ DONE this session |
| `kilo run` (one-shot) | `mavis run --mode=xxx "..."` | ✅ DONE this session |
| `kilo serve` (headless HTTP) | `mavis serve --port N` | ✅ DONE this session |
| `kilo providers` | `mavis provider list` (22 detected) | ✅ DONE this session |
| `kilo skills` | `mavis skills` (86 in mavis.items) | ✅ DONE this session |
| `kilo modes` (Code/Ask/Plan/Debug) | `mavis modes` (5 built-in modes) | ✅ DONE this session |
| `kilo mcp` (manage MCP) | `mavis mcp` (3 servers from mavis.json) | ✅ DONE this session |
| `kilo agent` (manage agents) | `mavis agents` (loads .md) | ✅ DONE this session |
| Built-in `code-savant` skill | `mavis run --mode=code` | ✅ already worked |
| Custom agent invocation | `mavis run --agent=<name>` | ✅ TESTED with cron-utility-checker |
| Kilo Gateway (provider routing) | direct OpenRouter + 7-provider mavis.json | ⚠️ PARTIAL — no gateway abstraction yet |
| Agent Manager (multi-session, worktrees) | mavis-swarm (parallel agents) | ⚠️ PARTIAL — no UI, no worktree isolation |
| `kilo mcp add <name>` | edit mavis.json + reload | ⚠️ MANUAL |
| `kilo attach <url>` | not implemented | ⏳ TODO |
| `kilo models` (list models) | not implemented | ⏳ TODO |
| `kilo stats` (token usage) | per-call usage printed | ⏳ AGGREGATE TODO |
| `kilo export/import` | not implemented | ⏳ TODO |
| `kilo db` (database tools) | Supabase mgmt API direct | ⏳ TODO |
| `kilo cloud` (multi-client sync) | mavis-swarm (multi-agent) | ⚠️ DIFFERENT — agents not clients |
| VS Code extension | n/a (Mavis is agent not IDE) | n/a |
| JetBrains plugin | n/a | n/a |
| KiloClaw (always-on agent) | Mavis IS the always-on agent | ✅ same concept |

---

## 2. Architecture comparison

### Kilo Code

```
┌─────────────────────────────────────────────┐
│  Clients (VS Code / JetBrains / CLI / Cloud)│
│  ↓ all talk to ↓                            │
│  kilo serve  ← HTTP + SSE via @kilocode/sdk│
│  ↓                                           │
│  Core engine (packages/opencode/)           │
│   ├─ agent runtime                          │
│   ├─ tools (read/edit/glob/grep/bash/...)  │
│   ├─ sessions (SQLite)                      │
│   └─ TUI                                    │
│  ↓                                           │
│  Kilo Gateway (kilo-gateway)                 │
│   └─ wraps 30+ providers, 500+ models       │
│  ↓                                           │
│  Provider APIs (Anthropic, OpenAI, ...)     │
└─────────────────────────────────────────────┘
```

### Mavis (now)

```
┌─────────────────────────────────────────────┐
│  Front door: Mavis root session (cloud)     │
│  ↓ routes work to ↓                         │
│  Sub-agents (task tool: explore/scout/...)  │
│  ↓                                           │
│  Agent roster (MaxClaw/Hermes/Claude/...)   │
│  ↓                                           │
│  mavis CLI  ←  mavis serve (HTTP)           │
│   ├─ provider routing (7 in mavis.json)     │
│   ├─ modes (5 built-in)                     │
│   ├─ agents (3 custom .md)                  │
│   ├─ skills (86 in mavis.items)             │
│   └─ MCP (3 servers from mavis.json)        │
│  ↓                                           │
│  OpenRouter (one API key, 100+ models)      │
│  + direct APIs (Anthropic, OpenAI, ...)     │
└─────────────────────────────────────────────┘
```

**Key difference:** Kilo Code has a long-running `kilo serve` daemon that all clients connect to. Mavis is session-oriented (M3 platform) and uses `communicate` for inter-agent messaging. The `mavis serve` HTTP mode is a thin shim for external clients (Telegram bot, scripts) to reach Mavis.

---

## 3. Provider routing

### Kilo

Kilo Gateway (`@kilocode/kilo-gateway`):
- Base URL: `https://api.kilo.ai/api/gateway`
- Drop-in OpenAI-compatible `/chat/completions`
- BYOK with encrypted storage
- Per-request cost/token tracking in microdollars
- Virtual `kilo-auto/*` models that route dynamically
- 30+ providers, 500+ models

### Mavis (today)

Mavis uses OpenRouter as the primary gateway. Other providers configured but not actively routed through a gateway.

```jsonc
// mavis.json — provider routing config
"provider": {
  "openrouter": {
    "env": ["OPENROUTER_API_KEY"],
    "options": {
      "apiKey": "$OPENROUTER_API_KEY",
      "baseURL": "https://openrouter.ai/api/v1",
      "provider": { "data_collection": "deny", "zdr": true }
    },
    "models": {
      "moonshotai/kimi-k3": { ... },
      "anthropic/claude-sonnet-4": { ... },
      ...
    }
  },
  "anthropic": { "env": ["ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN"] },
  "openai": { "env": ["OPENAI_API_KEY_1", "..."] },
  ...
}
```

**Gap:** no gateway abstraction layer. Mavis calls OpenRouter directly. If we want zero-markup inference like Kilo Gateway, we'd need to either (a) use Kilo Gateway as a provider, (b) build our own gateway, or (c) add a "smart route" function in mavis.py that picks the cheapest available provider per call.

---

## 4. Modes / Agents

### Kilo

Built-in: code, ask, plan, debug, review, orchestrator (deprecated — replaced by subagents).

Custom agents = markdown files in `.kilo/agents/<name>.md` with YAML frontmatter (`description`, `mode`, `model`, `temperature`, `displayName`, `color`, `steps`, `permission`).

### Mavis

Built-in (in `mavis.py` MODES dict): code, architect, ask, debug, orchestrator.

Custom agents = markdown files in `/workspace/mavis-cli/agents/<name>.md` with same frontmatter format.

3 .md agents shipped this session:
- `cron-utility-checker` (subagent) — runs the 5-question gate
- `dr-closeout-reviewer` (subagent) — audits DR Électrique dossiers
- `swarm-orchestrator` (primary) — Kimi K3-style dispatch

**Tested:** `mavis run --agent=cron-utility-checker` correctly evaluated a speculative cron and REJECTED it via the 5-question gate. Output matches the agent's system prompt contract.

---

## 5. MCP

### Kilo

Configured in `kilo.json` under `mcp` key. Two transport types (local STDIO, remote HTTP/SSE). Per-tool permissions via `permission` key.

Community marketplace at github.com/Kilo-Org/kilo-marketplace.

### Mavis

Configured in `mavis.json` under `mcp` key (same format as Kilo). 3 servers pre-loaded:
- `supabase` (remote) — `https://mcp.supabase.com/mcp`
- `github` (local) — `npx @modelcontextprotocol/server-github`
- `fetch` (local) — `npx @modelcontextprotocol/server-fetch`

**Gap:** no MCP execution layer. The config exists but `mavis` doesn't actually spawn/use MCP servers yet. Would need to add a `mavis mcp connect <name>` that starts the STDIO subprocess and proxies tool calls.

---

## 6. Context management

### Kilo

Tool-based (lazy), not upfront injection. `@file`, `@terminal`, `@git-changes`, `@` past chats. `.kilocodeignore` for exclusions. Codebase indexing optional.

### Mavis

mavis.items in Supabase acts as the persistent context (86 items: skills, capabilities, etc.). mavis-rag.py does semantic search over these. No @-mention UI (Mavis is chat-based, not file-based).

---

## 7. Skills (Kilo) ↔ Capabilities (Mavis)

### Kilo

7 skills in `.kilo/skills/` + 1 in `.kilocode/skills/`. Custom skills = markdown files.

### Mavis

85 hosted skills (this is Mavis's biggest asset over Kilo) + 8 memory topics + 14 capabilities in mavis.items. Plus skill_matcher.py for semantic search.

---

## 8. Pricing

### Kilo

- Free (BYOK/local)
- Teams $15/user/mo
- Enterprise (custom, SSO, audit)
- Kilo Pass ($19/$49/$199/mo credit subscriptions)
- 5% processing fee

### Mavis

No pricing — it's Francis's personal agent. All API costs are direct to provider (OpenRouter, Anthropic, etc.). No markup, no fee.

---

## 9. What Mavis should still adopt (TODO list)

Priority-ordered:

### P0 — make mavis CLI production-grade
- [ ] `mavis attach <url>` — connect to a running mavis server (multi-client like VS Code + JetBrains)
- [ ] `mavis models [provider]` — list available models per provider
- [ ] `mavis stats` — aggregate token usage / cost from log of `mavis run` calls
- [ ] `mavis config get/set` — read/edit mavis.json (currently read-only)
- [ ] Real MCP execution: `mavis mcp connect <name>` to spawn STDIO servers + tool routing
- [ ] Better kimi-k3 fallback (currently defaults to llama-3.1-70b; add per-model routing)

### P1 — close feature gaps with Kilo
- [ ] `mavis export/import` — session data JSON (Mavis already has this via mavis tool)
- [ ] `mavis db` — convenience wrapper around Supabase mgmt API
- [ ] `mavis upgrade` — version check + auto-update of mavis package
- [ ] `mavis cloud` — multi-device session sync (Tailscale-based; similar to Kilo's JWT share tokens)

### P2 — differentiate from Kilo
- [ ] Mavis Swarm: Agent Manager equivalent — multi-session dashboard with parallel agent orchestration (already have mavis-swarm; need UI)
- [ ] KiloClaw equivalent: always-on background agent (Mavis IS this on Francis's machines)
- [ ] Kilo Gateway equivalent: smart router that picks the cheapest available provider per call
- [ ] `@-mentions` adapted to chat: `@skills`, `@env`, `@mcp`, `@agents` for quick context injection

---

## 10. Files shipped this session

```
/workspace/mavis-cli/
├── mavis.py                    # 23KB, 11 subcommands, Kilo-style CLI
├── config/
│   └── mavis.json              # 150 lines, 7 providers + 5 agents + 3 MCP
└── agents/
    ├── cron-utility-checker.md # 5-question gate (TESTED, REJECTED speculative cron)
    ├── dr-closeout-reviewer.md # DR Électrique dossier auditor
    └── swarm-orchestrator.md   # Kimi K3-style orchestrator
```

Symlink: `/usr/local/bin/mavis` → `/workspace/mavis-cli/mavis.py`

---

## 11. Real test summary

| Test | Command | Result |
|------|---------|--------|
| Modes listed | `mavis modes` | 5 modes (code/architect/ask/debug/orchestrator) |
| Providers detected | `mavis provider list` | 22 unique providers |
| Skills found | `mavis skills` | 86 (85 + swarm_teams capability) |
| Skills semantic search | `mavis skills-rag "deploy a bun app"` | top match: `app-builder` (score 11.68) |
| Custom agent loaded | `mavis agents` | 3 .md agents |
| Code mode run | `mavis run --mode=code "retry 3x bash"` | ✅ returned bash function |
| Architect mode | `mavis run --mode=architect "Bun deploy"` | ✅ returned 3-strategy comparison |
| Custom agent run | `mavis run --agent=cron-utility-checker` | ✅ correctly REJECTED speculative cron |
| HTTP serve | `mavis serve --port 7741` | ✅ GET /health, GET /skills, POST /run all work |
| mavis.json validated | `mavis config` | ✅ valid JSON, 7 providers, 5 agents, 3 MCP servers |

---

## 12. Confidence + next steps

**Confidence:** HIGH on the Kilo Code architecture (verified via 2 deep sub-agent reports + my own source reading). MEDIUM on the Mavis parity (I shipped the surface but real production-grade needs the P0 TODO list).

**Next steps for Francis:**
1. Run `mavis agents` to see the 3 custom agents — try `mavis run --agent=swarm-orchestrator "your goal"` to test
2. Add more .md agents in `/workspace/mavis-cli/agents/` for your domains (e.g., `tender-reviewer.md`, `rfi-writer.md`)
3. Edit `/workspace/mavis-cli/config/mavis.json` to add providers or MCP servers
4. Test `mavis serve` from your Mac Mini (Tailscale) to use Mavis as a backend for local scripts
5. The P0 TODO list above is the next batch of work — pick what matters most to you

