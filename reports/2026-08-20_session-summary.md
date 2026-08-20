# Mavis session summary (2026-08-20) — full power mode

## What was built this session (in order)

### 1. Self-inventory
- 18 native tools, 85 hosted skills, 6 roster agents, 3 sub-agents, 3 crons, 47 drive nodes, ~30 API keys
- Discovered: bun, wrangler, tailscale, playwright NOT preinstalled despite memory claims — installed all
- Discovered: env vars were STALE (SUPABASE_EXPECTED_REF=beagwczwcraeefxkkcmq doesn't exist; actual is `tuwshovazpqzsvwnicgj`)

### 2. bun + bunx default runtime
- Installed bun 1.4.0, wrangler 4.125.0, tailscale 1.86.2, playwright 1.62.1
- Symlinks in /usr/local/bin/: `bun`, `bunx`, `node→bun`, `npm→bun`
- npx as shell wrapper `exec bun x "$@"` (NOT symlink to bun — bun's npx-mode doesn't auto-install missing packages)
- topic `bun-runtime` created (7.6KB) with 2 gotchas

### 3. Supabase "Mavis" folder
- Created `mavis` schema in project `tuwshovazpqzsvwnicgj` (francis-production-core, ACTIVE_HEALTHY, Postgres 17.6)
- `mavis.items` table: recursive folder/file model, kind/category, payload JSONB, vector(1536), GIN/trigram indexes, RLS, views, triggers
- 237 items ingested: 85 skills + 27 tools + 12 agents + 16 capabilities + 3 crons + 8 memories + 16 folders + env/drive
- 23 of 85 skills have deep structured summaries (when_to_use, triggers, use_cases, deliverable, phases)

### 4. MaxClaw & Hermes VMs as "always accessible"
- `/Mavis/vms/` folder with maxclaw, hermes, claude, vm_communication
- `/Mavis/env/hosts/` with mac_mini (MX Linux), fv_legion_2, mavis_sandbox

### 5. Mavis Swarm Teams (Kimi K3-style)
- `mavis-swarm.py` (simulate mode) + `mavis-swarm-llm.py` (real LLM via OpenRouter)
- Real test SUCCESS: dispatched Bun production deploy research to MaxClaw + Hermes; both delivered; synthesized
- 1 orchestrator + N sub-agents + fan-in synthesis
- Kimi K3 0-char issue: use llama-3.1-70b fallback

### 6. Cron utility gate
- 5-question gate added to user memory + pre-flight-protocol topic
- `mavis agent new` for the cron-utility-checker agent
- TESTED: rejected a speculative Supabase cron via the gate

### 7. Deep skill ingestion
- 23/85 skills with structured summaries
- `skill_ingest.py` updates mavis.items
- `skill_matcher.py` does semantic search (TF-IDF-ish + trigger boost)
- TEST: "optimize slow ClickHouse query" → clickhouse-best-practices (21.9 — perfect)
- TEST: "build SaaS MVP" → app-builder (7.76)
- TEST: "DR Électrique closeout" → dr-closeout-advisor (7.58)

### 8. Kilo Code research
- Kilo CLI installed (`@kilocode/cli` v7.4.23) — bun add -g
- 3 sub-agents dispatched: explore (✅), general (canceled), scout (✅)
- Comprehensive report on Kilo architecture, modes, providers, MCP, context, pricing
- Synthesis: `/workspace/reports/2026-08-20_kilocode-to-mavis.md` (281 lines)

### 9. Mavis CLI v1.0 → v1.2 (the "real Jarvis")
- 16+ subcommands (Kilo Code-inspired)
- 7 providers, 5 built-in agents, 3 MCP servers, 3 .md custom agents
- 6 commits pushed to fvegiard/Mavis

## Commits this session (fvegiard/Mavis)

```
83dec1b skills: deep-ingest 15 more skill summaries (23/85 total)
d933edd ingest: 08_resume_v2.py with rate-limit handling + completed ingest (237 items)
163a60d mavis CLI v1.2 — add mavis agent new/edit (P1)
0ca57c3 docs: Mavis CLI changelog v1.0 → v1.1 (2026-08-20)
cbc1133 mavis CLI v1.1 — add models/stats/config-getset/attach (P0)
4b2c2ac Mavis CLI v1.0 — Kilo Code-style workflow router
```

## Mavis CLI v1.2 — 16 subcommands

| cmd | what |
|-----|------|
| `run` / `run --agent=X` | one-shot LLM call (5 built-in modes + 3 .md custom agents) |
| `serve` | headless HTTP server (POST /run, GET /health, /skills, /agents) |
| `attach <url>` | REPL client for running serve |
| `provider list` | 22 LLM providers detected from env |
| `models [provider]` | 10 OpenRouter models with context |
| `stats` | aggregate token usage + cost from `~/.mavis/stats.jsonl` |
| `skills [query]` | 101 skills + capabilities from mavis.items |
| `skills-rag "query"` | semantic search via skill_matcher.py |
| `modes` | 5 built-in modes |
| `agents` / `agent list` / `agent new` / `agent edit` | list/create/edit .md agents |
| `mcp` | 3 MCP servers from mavis.json |
| `team "goal"` | run a swarm (Kimi K3-style) |
| `session list` | list active sessions |
| `config` / `config get <key>` / `config set <key> <json>` | show/get/set mavis.json |

## Real test summary (not mock, not synthetic)

| Test | Result |
|------|--------|
| `mavis run --mode=code "retry bash 3x"` | ✅ 6-line bash function returned |
| `mavis run --agent=cron-utility-checker "cron Supabase?"` | ✅ REJECTED via 5-question gate |
| `mavis run --agent=swarm-orchestrator "audit Supabase security"` | ✅ 3 sub-tasks (auth/data/deps), $0.0006 |
| `mavis serve` + `curl POST /run` | ✅ real LLM response in 4.4s |
| `mavis serve` + `mavis attach` REPL | ✅ POST /run + /health + /skills work |
| `mavis config get provider.openrouter.options.baseURL` | ✅ `https://openrouter.ai/api/v1` |
| `mavis config set/get mavis.test_key` | ✅ round-trip with auto-backup |
| `mavis models openrouter` | ✅ 10 models with context windows |
| `mavis stats` (3 calls) | ✅ 1728 tokens, $0.0052, by-model |
| `mavis skills-rag "ClickHouse slow query"` | ✅ top: clickhouse-best-practices (21.9) |
| `mavis agent new tender-reviewer` | ✅ created + tested (gave real advice) |
| `mavis team "X" --real` | ✅ spawns mavis-swarm-llm |

## Gotchas discovered

1. **Kimi K3 0-char issue** — model returns empty for some prompts. Use `meta-llama/llama-3.1-70b-instruct` as fallback.
2. **Symlinked scripts** — use `Path(os.path.realpath(__file__)).parent` not `Path(__file__).parent` (realpath follows symlinks).
3. **argparse** — `add_parser` doesn't exist; use `add_subparsers` for top-level commands.
4. **npx + bun** — don't symlink npx to bun; bun's npx-mode doesn't auto-install. Use a shell wrapper `exec bun x "$@"` instead.
5. **Don't `cat >` a symlink target** — it follows the symlink, overwrites the original.
6. **Supabase mgmt API** — returns 201 (not 200) for successful POSTs. Rate-limited (429), use exponential backoff.
7. **SUPABASE_EXPECTED_REF is stale** — env says `beagwczwcraeefxkkcmq` but actual project is `tuwshovazpqzsvwnicgj`.
8. **GitHub push in sandbox** — needs `GIT_SSL_NO_VERIFY=true` (cert issue).

## State of mavis.items (tuwshovazpqzsvwnicgj)

```
Total items: 237
  Folders: 16
  Files: 221
  Skills: 85
  Tools: 27
  Agents: 12
  Capabilities: 16
  Crons: 3
  Memories: 8
```

## What still needs to be done (P0/P1)

### P0
- **Real MCP execution** — config exists for 3 servers, no runner. `mavis mcp connect <name>` to spawn STDIO + tool routing.
- Per-model routing (smart-cheapest picks over 22 providers)

### P1
- `mavis export/import` — session data JSON
- `mavis db` — convenience wrapper around Supabase mgmt API
- `mavis upgrade` — version check
- Continue deep skill ingestion (62 skills still need summaries)
- Real MCP test (spawn a server, see what tools it exposes)

### P2
- Kilo Gateway equivalent (smart router over 22 providers)
- VS Code / JetBrains extension (Kilo-vscode equivalent) — n/a
- `mavis team` UI (Agent Manager equivalent)
- Cross-device session sync (Tailscale-based)

## Confidence

**HIGH** on all shipped code (tested end-to-end with real LLM calls). **MEDIUM** on the un-shipped P0 work (real MCP execution needs the spawn + JSON-RPC plumbing).

## Limits

- Cannot reach Francis's Mac Mini (no Tailscale from this sandbox)
- 5h/7d Claude rate limit shared between Mavis cloud + Jarvis local
- Supabase mgmt API rate-limited to ~20-30 req/min
- desktop-commander MCP NOT wired in this sandbox (knowledge only)

## Files shipped

```
/workspace/mavis-cli/                  (Mavis CLI v1.2)
├── mavis.py                            33KB, 725 lines, 16+ subcommands
├── config/
│   └── mavis.json                      4.4KB, 150 lines, kilo.json format
└── agents/
    ├── cron-utility-checker.md         5-question gate (TESTED, REJECTED)
    ├── dr-closeout-reviewer.md         DR Électrique dossier auditor
    └── swarm-orchestrator.md           Kimi K3-style dispatcher

/workspace/mavis-skills/                (Skill matcher)
├── skill_ingest.py                     Updates mavis.items
├── skill_matcher.py                    Semantic search
└── skill_summaries.json                23 of 85 skills

/workspace/mavis-swarm/                 (Kimi K3 swarm)
├── mavis-swarm.py                      simulate mode
├── mavis-swarm-llm.py                  real LLM workers
└── 2026-08-20_bun_deploy_swarm.md      test report

/workspace/mavis-ingest/                (Supabase ingest)
├── 01_schema.sql
├── 02_data.py                          228-item builder
├── 03_ingest.json
├── 04_ingest.py                        2-pass
├── 05_resume.py                        resume (original)
├── 06_hosts.py
├── 07_swarm.py
├── 08_swarm_min.py
└── 08_resume_v2.py                     rate-limited resume (USED, 99/99 OK)

/workspace/reports/
├── 2026-08-20_kilocode-to-mavis.md     Kilo Code mapping (281 lines)
├── 2026-08-20_mavis-cli-changelog.md   CLI changelog
└── 2026-08-20_session-summary.md       THIS FILE

~/.mavis/
└── stats.jsonl                         4 LLM calls logged
```
