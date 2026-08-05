# Mavis — Agent Brief (root AGENTS.md)

> AGENTS.md is the cross-vendor standard for AI agent instructions
> (Linux Foundation Agentic AI Foundation, Dec 2025). Read by Claude Code,
> Cursor, GitHub Copilot Coding Agent, and other agent surfaces.
> Pattern: https://www.iuriio.com/blog/posts/2026/05/agents-md-field-guide-2026

## What this repo is

Mavis is a **quantum agentic orchestrator** — Claude API + RAG + multi-LLM
router + 18 mavis-* tools. Personal AI stack for Francis Végiard.
License: MIT. Live at https://github.com/fvegiard/Mavis.

## Stack (verified working 2026-08-05)

- Node 26.6.0, Python 3.14.5, npm 12.0.2
- Claude Code 2.1.221
- Supabase `hzdzeleznvxzncgzqiub` (132 RAG vectors)
- Tailscale tailnet `fvegiard@github`

## Build & test

```bash
cd /workspace/jarvis
make install    # sets up venv and pre-commit
make test       # runs pytest in tests/
make lint       # pre-commit hooks (ruff, secrets, large files)
make rag Q="…"  # quick RAG query
make commit M="…"  # Kimi K2.7 review + commit
```

## LLM provider order (NEVER change without an issue)

1. **openrouter-free** (Nemotron 3 Ultra 1M context, default)
2. **claude-oauth** (paid, premium — needs `"You are Claude Code..."` system + `claude-code-20250219` beta header)
3. **copilot** — RESERVED for `mavis-commit` git commits and code review (Kimi K2.7 default, Opus 4.7 via `--premium`)
4. **groq** (fastest, Llama 3.3 70B)
5. **openrouter** (variety)

## Hard rules for agents

- **DO NOT** edit `prompts/SOUL.md` or `prompts/CONSTITUTION.md` — read-only at runtime
- **DO NOT** edit `mavis-commit.py` without an approved issue
- **DO NOT** put the current date in the system prompt — it kills the KV cache
- **DO NOT** remove tools from the system prompt mid-session — invalidates the cache
- **DO** add tools to `scripts/mavis_<name>.py` and register in `scripts/__init__.py`
- **DO** use the 4-element tool description template: action, input prereq, output expectation, when-to-pick
- **DO** annotate every MCP tool with `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint`
- **DO** emit `cache_control: {type: "ephemeral", ttl: "1h"}` on every Claude call

## Process rules (enforcement map in `prompts/PROCESS_RULES.md`)

1. `ruff check` MUST pass before claiming any Python file done
2. Visual verification on rendered output (PDF/image/UI)
3. Reflexion v2: generate → critic (different model) → revise, max 2 rounds
4. Sandbox persistence: push to Supabase + copy to `/root/`
5. Agent autonome: when Francis says go, GO
6. Never ask for new auth keys — use only what exists in the vault
7. Web/GitHub search BEFORE writing non-trivial code
8. Never trust model self-description (cross-check `platform.claude.com/docs`)
9. Skill minimization: never suggest 23 dropped, ask before 8 borderline
10. Prefix `🔴` for OAuth errors or fallback use

## Secrets

- API keys live in `.env` (gitignored) or GitHub Actions secrets — never in code
- If you find a secret, run `git filter-repo` and rotate it
- The vault list: `~/.mavis/secrets/` (per-project) + env vars
- See `SECURITY.md` for the full 5-layer defense model

## Tool description template (REQUIRED for new MCP tools)

```python
{
    "name": "mavis_<verb>_<noun>",
    "description": "<action>. <input prereq>. <output expectation>. <when to pick vs alternatives>.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "field1": {"type": "string", "description": "..."},
            ...
        },
        "required": ["field1"]
    },
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
}
```

## Git workflow

- `main` is production. PRs only.
- Use `mavis-worktree` for isolated feature work.
- Use `mavis-commit --push` for review + commit + push in one.
- Conventional commits: `feat(scope): …`, `fix(scope): …`, `docs: …`, `chore: …`, `deps: …`
- One commit per logical change. Small commits > large commits.

## Testing

- Every PR must run `make test` and pass
- 47 unit tests in `tests/` (growing to 50+ in v10.0)
- Smoke test imports + executable check for all 18 mavis-* tools
- Lint must be clean (`ruff check`)

## Communication

- File issues at https://github.com/fvegiard/Mavis/issues
- Use `mavis-a2a` for agent-to-agent comms
- Use `mavis-skill` to discover/install skills
- Francis's preferred language: French/English. Direct, peer-to-peer.

## Sub-agents

- `Hermes` — research and retrieval specialist
- `MaxClaw` — code and infrastructure specialist
- `Verifier` — critical reviewer (premium model)
- See `prompts/AGENTS.md` for briefs and routing

## Don't

- Suggest 23 dropped skills (full list in `prompts/PROCESS_RULES.md` §9)
- Suggest 8 borderline skills without asking first
- Use "never" or "don't" in new rules — use decision criteria instead
- Pre-fill tool definitions with timestamps
- Cache `cache_read_input_tokens` and `cache_creation_input_tokens` separately in cost tracking

## Provenance

- Created 2026-08-05 during ultra-research session
- Pattern: AGENTS.md Field Guide 2026 (Linux Foundation, Dec 2025)
- Sibling files: `CLAUDE.md` (Claude Code-specific), `prompts/SOUL.md` (identity), `prompts/SYSTEM_PROMPT.md` (task)
