# Jarvis (Mavis) — Project Memory

## Project: Mavis / Jarvis
- Purpose: Quantum agentic orchestrator (Claude + RAG + multi-LLM router)
- Author: Francis Végiard
- AI: Mavis (this is the agent's own project)

## 16 mavis-* tools (all `ruff check` 0 errors)
See /root/.claude/CLAUDE.md for the full list.

## Development
- Install: `make setup`
- Test: `make test` (47 tests)
- Lint: `make lint` (ruff)
- RAG query: `make rag Q="..."`
- Commit: `make commit M="..."` (uses Copilot review)

## Conventions
- Python 3.11, ruff 0.16.1
- All scripts in scripts/ must be executable
- No hardcoded secrets — use env vars
- Use `mavis-call` for Claude (OAuth pool unlocked)
- Use `mavis-rag` for knowledge base queries
- Use `mavis-commit --push` for git workflow

## Hard rules
- Never bypass the 16 mavis-* wrappers (use them)
- Always test before commit (make test)
- Always lint before commit (make lint)
- Use mavis-rag before inventing — knowledge is already there
