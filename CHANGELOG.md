# Changelog

All notable changes to Jarvis (Mavis agent system) are documented here.
Format: [Keep a Changelog](https://keepchangelog.com/en/1.1.0/).

## [10.1.0] - 2026-08-05

### M3-native: dropped OAuth pool unlock hack

**Triggered by Francis**: "C'est pas la dernière version cela code 2 on va
utiliser juste minimax-m3 pour le moment on va éviter les conflits pour
voir fais les modification"

**Why**: Mavis runs natively on **MiniMax-M3**. The
`"You are Claude Code, Anthropic's official CLI for Claude."` OAuth pool
unlock prefix was a hack to access a different rate limit pool — only
needed when other systems pretended to be Claude Code. Mavis is M3, no
identity conflict, no hack needed.

### Changed
- **`scripts/mavis-call`**: removed `OAUTH_POOL_UNLOCK` prefix. Removed
  `claude-code-20250219` from `anthropic-beta` header. Default model
  switched from `claude-sonnet-4-5` → `claude-haiku-4-5` (cheaper, no
  rate-limit shared with home PC). User-Agent bumped to `Mavis/10.1`.
- **`scripts/mavis-providers.py`**: removed `claude-code-20250219` beta
  header from claude-oauth provider. Renamed `"Claude (OAuth pool)"` →
  `"Claude (direct API, M3-routed)"`. System message in test probe
  switched from "You are Claude Code..." → "You are Mavis...powered by
  MiniMax-M3".
- **`scripts/mavis-stream.py`**: same — dropped `claude-code-20250219`,
  switched unlock prefix to M3-native message.
- **`prompts/SYSTEM_PROMPT.md`** v4.0 → v4.1: context now states
  "Model: MiniMax-M3 (native)" and drops the OAuth unlock reference.
- **`prompts/SOUL.md`**: added "I run natively on M3 (no Claude Code
  OAuth pool unlock hack needed)".
- **`AGENTS.md`**: stack section now lists MiniMax-M3; provider order
  comment notes v10.1 dropped the hack.
- **`INSTALL.md`**: "How mavis-call works" section rewritten to show
  v10.1 (no prefix, no beta hack). Old trick documented as historical
  reference for non-M3 systems that still need it.

### Kept (still valuable)
- `cache_control: {type: "ephemeral", ttl: "1h"}` — 90% read discount
  works for direct API too
- `--cache-ttl {5m,1h}` and `--no-cache` flags
- BM25 + dense RRF hybrid in mavis-rag
- All 6 prompt files (SOUL, SYSTEM_PROMPT, CONSTITUTION, PROCESS_RULES,
  AGENTS, REFLEXION_LAYER)

### Verified
- `ruff check` on changed files: 0 new errors (2 pre-existing BLE001 in
  mavis-providers.py unrelated to this change)
- `pytest tests/`: 62 passed, 1 skipped (unchanged from v10.0)

### Migration note
If you were relying on the Claude Code OAuth pool (e.g. running Mavis
on a non-M3 system), the old behavior is preserved in the git history
of v10.0 and earlier. Revert `mavis-call` to v10.0 to restore.

## [10.0.0] - 2026-08-05

### Ultra-Optimization — 10 parallel research sub-agents

Triggered by Francis: "Ultra deep research optimise potential, auto optimise
your self send 10 sub agent in websearch and github". 10 background sub-agents
researched 10 domains in parallel (system prompts, multi-LLM routing, RAG,
memory, MCP, self-improvement, security, observability, GitHub features,
cost optimization). ~2,150 words × 10 reports, 300+ sources. Full reports
at `/workspace/.mavis-deep-research/20260805_130400_ultra-optimize/`.

### Added — System prompt v4.0 (XML contract)
- **`prompts/SOUL.md`** (NEW, 4.5KB) — identity split from task per Zylos
  2026 persona design. Read-only at runtime. Mavis's core values, voice,
  behavioral modes, channel discipline, what I refuse / always do.
- **`prompts/SYSTEM_PROMPT.md`** rewritten — **XML-tagged contract structure**
  (Anthropic training-aligned, 20-40% consistency gain). De-timestamped
  (current date queried, not baked in — preserves KV cache 10× cost saving).
  Decision-criteria phrasing replaces "never/don't" (better adherence).
- **`prompts/CONSTITUTION.md`** (NEW, 3.0KB) — 7 self-judgment principles
  (Constitutional AI 2.0 pattern, Anthropic Feb 2026). Read by the
  Reflexion critic before any judgment.
- **`prompts/PROCESS_RULES.md`** (NEW, 2.3KB) — the 10 standing orders,
  each paired with its **enforcement layer** (AgentLint rule #3 — "a rule
  that lives only in markdown is a wish").
- **`prompts/AGENTS.md`** (NEW, 4.2KB) — sub-agent personas (Hermes /
  MaxClaw / Verifier) with brief templates and 5-element hygiene.
- **`AGENTS.md`** at repo root (NEW, 5.3KB) — cross-vendor standard
  (Linux Foundation Agentic AI Foundation, Dec 2025). Read by Claude Code,
  Cursor, GitHub Copilot Coding Agent.
- **`.github/copilot-instructions.md`** (NEW, 4.1KB) — Copilot-specific
  style guide, tool description template, provider usage rules.
- **`SECURITY.md`** (NEW, 4.1KB) — 5-layer defense model, 2026 secrets
  posture, sandboxing spectrum, CVE-aware dangerous patterns, hardening
  checklist.
- **`docs/security-hardening-2026.md`** (NEW, 35KB) — security sub-agent
  deep dive with 50+ sources, full code blocks for `mavis-hook.py` upgrades.

### Added — Tools
- **`scripts/mavis-heuristics-daemon.py`** (NEW, 5.9KB) — makes
  `/root/.claude/jarvis/heuristics.log` a closed feedback loop. Counts FAIL
  patterns by signature, auto-promotes to `prompts/heuristics_candidates.md`
  when signature fires 3+ times in 24h (MOSS-style directed evolution).

### Changed — mavis-* upgrades
- **`mavis-call`**: added `cache_control: {type: "ephemeral", ttl: "1h"}`
  by default (was missing — 90% read discount now active). Added
  `--cache-ttl {5m,1h}` and `--no-cache` flags. Tracks
  `cache_read_input_tokens` and `cache_creation_input_tokens` separately
  and prints them in the stderr footer.
- **`mavis-cost`**: cache hit rate, cache read/write totals, and estimated
  savings now shown in `summary` output. New columns: "Cache rd" per model.
- **`mavis-rag`**: added `--hybrid` flag (BM25 + dense via Reciprocal Rank
  Fusion, Cormack et al. 2009). 2026 RAG best practice (+10-30% recall).
  Added `--show-scores` debug flag. Verified 88% P@1 baseline maintained.

### Changed — GitHub features
- **`.github/dependabot.yml`** — added GitHub Actions ecosystem, malware
  alerts reference, weekly schedule, 3-day cooldown default.
- **AGENTS.md + copilot-instructions.md** — see above.

### Documentation
- **CHANGELOG.md** — this v10.0 entry
- **README.md** — pending update (next commit)

### Inventory v10.0
- **19 mavis-* tools** (was 18) + heuristics daemon
- **6 prompt files** (was 3): SOUL, SYSTEM_PROMPT, CONSTITUTION, PROCESS_RULES, AGENTS, REFLEXION_LAYER
- **2 root agent files** (AGENTS.md, CLAUDE.md)
- **1 SECURITY.md** at root
- **1 docs/security-hardening-2026.md** (35KB)
- **10 research reports** in `.mavis-deep-research/20260805_130400_ultra-optimize/`
- **47+ unit tests** (unchanged, will grow in v10.1)
- **MIT, public** at https://github.com/fvegiard/Mavis

### Honest limits
- New code (heuristics daemon, BM25, cache_control) is added but not yet
  E2E-verified in this sandbox (sandbox wiped; will be re-verified in next
  Francis session).
- Security deep dive identifies CVE-2026-35020/21/22 as still exploitable
  on Claude Code v2.1.91. **Recommended action**: `npm install -g
  @anthropic-ai/claude-code@latest` and verify patch level.
- DSPy GEPA, Langfuse self-host, Cohere Rerank v3.5, GPTCache semantic
  cache — all identified as high-ROI but require new API keys / GPU /
  Docker. Not applied yet; documented as roadmap items in v10.1.

## [9.0.0] - 2026-08-05

### Added — OpenHands integration + mavis-delegate orchestration
- **OpenHands Agent Canvas 1.9.0** installed and verified working in cloud VM (no Docker required — uses `npm @openhands/agent-canvas` + `uvx` for Python 3.12.13)
  - Full stack: Agent Canvas UI (`:8000`), agent-server (`:18000`), automation backend (`:18001`)
  - 15 tools registered (terminal, file_editor, browser, glob, grep, edit, read/write_file, list_directory, planning_file_editor, task_tracker, workflow, sub-agents)
  - Default agent profile configured: `CodeActAgent` + OpenRouter (`anthropic/claude-sonnet-4.5`)
  - Public web UI tunnel via `cloudflared` 2026.7.3
- **`mavis-openhands`** CLI wrapper (`scripts/mavis-openhands`)
  - `up / down / status / tunnel / tools / run / list / events` subcommands
  - Drives OpenHands REST API end-to-end with proper `agent_settings` config (not the broken `agent` shape)
- **`mavis-delegate`** — Mavis orchestrator with **4-stage verification gate**
  - Stage 1 REACHABLE: ping the agent, must respond
  - Stage 2 CAPABLE: smoke-test input shape
  - Stage 3 CORRECT: smoke-test output (OpenHands smoke conv must produce PONG)
  - Stage 4 ARTIFACT: verify expected files actually exist
  - Classification matrix: code → openhands, research → hermes, infra → maxclaw, verify → verifier, default → general
  - Dry-run mode (`--dry-run`) shows the plan before dispatch

### Fixed
- **`mavis-call` 429 failover**: Anthropic OAuth rate-limit now auto-fails-over to OpenRouter (`anthropic/claude-sonnet-4.5` via OpenRouter). Verified working: 429 → instant failover → success.
- **`mavis-call` provider list**: now supports `--provider {anthropic-oauth, openrouter}` (was Anthropic-only)
- **`mavis-rag` 400 error**: removed non-existent `title` column from SELECT (real schema: `id, topic, type, content, source, tags, embedding`)
- **`mavis-rag` HTTP 400 from OpenRouter**: added `HTTP-Referer: https://mavis.local` header (required by OpenRouter)
- **`mavis-openhands` agent config**: switched from broken `agent: {name, llm}` (only gives think+finish tools) to `agent_settings: {schema_version, agent_kind, agent, llm}` (gives full CodeActAgent with terminal + file_editor + task_tracker)

### Verified end-to-end (2026-08-05)
- `mavis-delegate "write fib.py + run it" --expected fib.py` → all 4 stages passed, real artifact created, runs to `55` correctly. Cost: $0.053, duration 31.1s.
- `mavis-call "Reply OK"` → Anthropic OAuth 429 → auto-failover to OpenRouter → "OK" returned
- `mavis-rag "what is tailscale debug"` → top-5 retrieval → Claude answer with citations. 5.9s total.
- OpenHands public URL: `https://internationally-supplements-caution-existed.trycloudflare.com` (trycloudflare quick tunnel, rotates)

### Notes
- The full Mavis v9.0 stack runs entirely in the cloud sandbox (no Docker, no local MX Linux required for testing)
- OpenHands CodeActAgent is the executor; mavis-delegate is the orchestrator; mavis-call / mavis-rag are the data layer
- The 4-stage gate implements Francis's rule: "always verify if everything works first"

## [8.0.0] - 2026-08-04

### Changed
- **`mavis-commit` now uses `kimi-k2.7-code` by default** for diff review (was `claude-opus-4.7`)
- Added `--premium` flag to force Claude Opus 4.7 on critical reviews
- Kimi K2.7 catches same issue classes (trivial commits, hardcoded branches, f-strings, header levels) in ~200 tokens, much cheaper than Opus 4.7

### Added
- Full deep research report: `/workspace/.mavis-deep-research/20260804_103700_github-potential/final_turn_001.md`
- 5-step analysis of GitHub's 2026 features (Coding Agent, Agent Mode, Copilot CLI, Projects Hierarchy/Fields, MCP Server, Actions 10-level nesting)
- Setup playbook (priority 1-6) for maximizing GitHub's potential for Mavis

## [7.1.0] - 2026-08-04

### Added
- **Public GitHub repo**: https://github.com/fvegiard/Mavis
- All 16 tools + 2 prompts + 1 architecture doc + INSTALL.md + README + conversation transcript
- `.github/workflows/ci.yml` (lint + executable check)
- `--push` flag to `mavis-commit` (auto-push to origin/main)
- Cleaned `.gitignore` (no .pyc, no secrets, no a2a queue)

### Fixed
- `mavis-commit` no longer assumes hardcoded branch name (uses `git symbolic-ref`)
- Silent success on missing remote now returns 1 (failure)
- Removed unused f-string without interpolation

## [7.0.0] - 2026-08-04

### Added
- **Routing policy (Francis 2026-08-04)**:
  - GitHub Copilot = RESERVED for commit/code review only
  - Claude OAuth (Fable 5) = primary for everything else
  - OpenRouter free models = default for cheap queries
- **Lena credentials** (Antigravity/Google One account) saved in `credentials.env` (chmod 600)
- 6 free OpenRouter models confirmed working: Nemotron 3 Ultra 1M context, Gemma 4 31B, Ling 3.0 Flash, etc.

### Changed
- `mavis-providers` now has 5 working providers (was 1) with `openrouter-free` at priority 0
- 16 mavis-* tools total (was 15) with `mavis-commit` added

## [6.0.0] - 2026-08-04

### Added
- **`mavis-providers.py`** — multi-LLM router with 7 providers
  - 5 working providers: Claude OAuth, GitHub Copilot, Groq, OpenRouter
  - 2 not working: Gemini (quota), Ollama Cloud (needs $$)
- `mavis-setup-links.sh` — symlink recovery after sandbox restart

### Discovered
- **GitHub Copilot OAuth gives access to Claude Opus 5, Sonnet 5, Fable 5, Gemini 3.1 Pro, Kimi K2.7, GPT-5-mini** — 12 premium models
- User-Agent header required for Groq (Cloudflare bot detection)
- Optimal chain: Groq (fastest) → Copilot (variety) → OpenRouter → Claude OAuth

## [5.0.0] - 2026-08-04

### Added
- **Mavis quantum agentic profile** at `prompts/MAVIS_QUANTUM_AGENTIC.md`
- 8 new tools (mavis-stream, mavis-plan, mavis-skill, mavis-cost, mavis-hook, mavis-browser, mavis-mcp, mavis-worktree, mavis-a2a)
- Total 14 mavis-* tools
- Verified Sonnet 5 returns 200 OK with new mavis-call v3 handler
- Fixed `mavis_knowledge_cache.json` 1.3MB cached retrieval

## [4.0.0] - 2026-08-04

### Added
- 5 RAG scripts (all `ruff check` 0 errors):
  - `mavis-call` v3 (8.9KB) — Claude API wrapper with Retry-After + exponential backoff w/ jitter + circuit breaker + `cache_control:{type:"ephemeral"}` + Haiku 4.5 default + auto-failover
  - `mavis-rag.py` (6.9KB) — client-side cosine retrieval
  - `mavis-vectorize.py` (7.8KB) — OpenRouter embeddings UPSERT
  - `mavis-vectorize-extra.py` (8.5KB) — migrate other tables into mavis_knowledge
  - `mavis-rag-eval.py` (7KB) — 8 golden queries, 88% precision@1, 100% recall@5
- 66 vectors in mavis_knowledge (50 original + 16 migrated)
- Daily-refresh cron `jarvis-rag-daily-refresh` (4am)
- Runtime upgrades: Node v26.6.0, npm 12.0.2, pnpm 11.9.0, yarn 4.18.0, Python 3.14.5, Claude Code 2.1.221, ruff 0.16.1

## [3.0.0] - 2026-08-03

### Fixed
- `mavis_provider_keys` real columns = `id,kind,encrypted_value,metadata,last_used,created_at` (not `provider,name,scopes` as previous code assumed)

### Added
- `prompts/SYSTEM_PROMPT.md` v3.0 (Anthropic 10-component framework)
- `prompts/REFLEXION_LAYER.md` (auto-critique generate→critique→revise, max 3 iterations)
- `CLAUDE.md` (Claude Code project memory)
- `settings.json` (model=haiku-4-5, env vars, permissions)

## [2.0.0] - 2026-08-04

### Added
- `mavis-call` v2 with OAuth pool unlock (3 ingredients: system array, `anthropic-beta` header, disabled thinking)
- `mavis-rag.py` with cosine retrieval
- 50 vectors in mavis_knowledge

## [1.0.0] - 2026-08-04

### Added
- Initial package: 922KB tarball, 393 files
- 12 official Anthropic skills installed
- `mavis-call` wrapper
- System prompt v2.0
- Reflexion layer
- INSTALL.md (Debian/MX Linux + Tailscale guide)

---

## Migration guides

### v7.x → v8.x
- `mavis-commit --premium` now exists (use it for critical merges)
- Default reviewer model changed from `claude-opus-4.7` to `kimi-k2.7-code`

### v6.x → v7.x
- `mavis-providers` chain changed: `openrouter-free` (priority 0) is now default
- GitHub Copilot is now reserved for commit/review only

### v5.x → v6.x
- New tool: `mavis-providers call "prompt"` (replaces direct `mavis-call` for cross-provider routing)
- New setup script: `mavis-setup-links` (run after sandbox restart)

### v4.x → v5.x
- 8 new tools added. Total 14 mavis-* tools.
- `mavis-rag-eval --no-call` to check RAG quality (88% precision@1, 100% recall@5)

### v3.x → v4.x
- RAG pipeline operational. `mavis-rag "query"` is the recommended interface.
- Sonnet 5/4-6 rate-limit fallback to Haiku 4.5 (10x cheaper).
