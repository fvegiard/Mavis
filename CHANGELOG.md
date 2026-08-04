# Changelog

All notable changes to Jarvis (Mavis agent system) are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
