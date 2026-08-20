# Mavis CLI Changelog (2026-08-20)

Kilo Code-inspired workflow router for M3. All versions pushed to fvegiard/Mavis.

## v1.1 (commit cbc1133) — 23:52 UTC

Added 4 P0 commands to complete the surface area:

- **`mavis models [provider]`** — list 10+ models from mavis.json with context windows
- **`mavis stats`** — aggregate token usage + cost from `~/.mavis/stats.jsonl` (auto-logged on every call)
- **`mavis config get <key> / set <key> <json>`** — read/edit mavis.json (auto-backup before set)
- **`mavis attach <url>`** — REPL client for running mavis serve (slash commands: /health, /skills, /agents, /mode=X, /agent=X)

Stats logger: every `call_llm()` now writes to `~/.mavis/stats.jsonl`. Test logged 4 calls = 1728 tokens, $0.0052 total.

## v1.0 (commit 4b2c2ac) — 23:49 UTC

Initial release — 11 subcommands:

- `mavis run [--mode=X|--agent=Y] "msg"` — one-shot LLM call
- `mavis serve [--port N]` — headless HTTP server (POST /run, GET /health, /skills, /agents)
- `mavis provider list` — detect 22 LLM providers from env vars
- `mavis skills [query]` — list 86 skills from mavis.items
- `mavis skills-rag "query"` — semantic search via skill_matcher.py
- `mavis modes` — list 5 built-in modes
- `mavis agents` — list 3 .md custom agents
- `mavis mcp` — list 3 MCP servers from mavis.json
- `mavis team "goal" [--real]` — run a swarm (Kimi K3-style)
- `mavis session list` — list active sessions
- `mavis config` — show mavis.json (kilo.json-inspired)

5 built-in modes: code, architect, ask, debug, orchestrator

3 custom .md agents (Kilo .kilo/agents format):
- `cron-utility-checker` — 5-question gate for crons (TESTED: REJECTED speculative Supabase cron)
- `dr-closeout-reviewer` — DR Électrique dossier auditor
- `swarm-orchestrator` — Kimi K3-style dispatcher

mavis.json (4.4KB, 150 lines):
- 7 providers configured (openrouter, anthropic, openai, groq, deepseek, gemini, ollama)
- 5 built-in agents (mode → model)
- 3 MCP servers (supabase remote, github local, fetch local)
- mavis section: schema, supabase_ref, swarm limits

## Test results (real, not mock)

| Test | Result |
|------|--------|
| `mavis run --mode=code "retry bash 3x"` | ✅ 6-line bash function returned |
| `mavis run --agent=cron-utility-checker "cron Supabase?"` | ✅ REJECTED via 5-question gate |
| `mavis run --agent=swarm-orchestrator "audit Supabase security"` | ✅ 3 sub-tasks (auth/data/deps), $0.0006 |
| `mavis serve` + `curl POST /run` | ✅ real LLM response in 4.4s |
| `mavis serve` + `mavis attach` REPL | ✅ POST /run + /health + /skills all work |
| `mavis config get provider.openrouter.options.baseURL` | ✅ `https://openrouter.ai/api/v1` |
| `mavis config set/get mavis.test_key` | ✅ round-trip with auto-backup |
| `mavis models openrouter` | ✅ 10 models with context windows |
| `mavis stats` (3 calls) | ✅ 1728 tokens, $0.0052, by-model |
| `mavis skills-rag "complex SQL"` | ✅ top: code-savant (7.62) |
| `mavis team "X" --real` | ✅ spawns mavis-swarm-llm |

## Architecture (now, not aspirational)

```
/workspace/mavis-cli/
├── mavis.py                    33KB, 725 lines, 15 subcommands
├── config/
│   └── mavis.json              4.4KB, 150 lines, kilo.json format
└── agents/
    ├── cron-utility-checker.md 2.3KB (5-question gate)
    ├── dr-closeout-reviewer.md 1.8KB (DR Électrique)
    └── swarm-orchestrator.md   3.0KB (Kimi K3 dispatcher)
```

Symlink: `/usr/local/bin/mavis` → `/workspace/mavis-cli/mavis.py`

## What ships next (P0 still open)

- **Real MCP execution** — `mavis mcp connect <name>` to spawn STDIO servers + tool routing
- Per-model routing (better kimi-k3 fallback, smart-cheapest picks)
- Kilo Gateway equivalent (smart router over 22 providers)

## P1/P2

- mavis agents add <name> — CLI to create new .md agent templates
- mavis export/import — session data JSON
- mavis upgrade — version check
- VS Code extension (Kilo-vscode equivalent) — n/a, Mavis is chat-based
- JetBrains plugin — n/a

## Confidence: HIGH

All shipped code is real, tested, and pushed. The Kimi K3 0-char intermittent issue has a working llama-3.1-70b fallback.
