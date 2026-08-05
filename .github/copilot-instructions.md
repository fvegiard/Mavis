# Mavis — Copilot Instructions

> Read by GitHub Copilot in IDEs, Copilot CLI, Copilot code review,
> Coding Agent, and `@github` chat. Sibling to root `AGENTS.md` (which is
> the cross-vendor standard). This file is the Copilot-specific style guide.
> Pattern: docs.github.com — Adding repository custom instructions.

## Style

- **Comments**: explain **why**, not what. Code is read top-to-bottom; intent is in the comments.
- **Naming**: snake_case for files and functions, PascalCase for classes, SCREAMING_SNAKE for constants.
- **Line length**: 100 chars (ruff default).
- **Imports**: stdlib first, third-party second, local third. One blank line between groups.
- **Type hints**: required on all public functions. Use `Optional[T]`, `list[T]`, `dict[K, V]`.
- **Error messages**: one line. Format `ERROR <code>: <description>`. No emoji in error text.
- **Docstrings**: Google style for Python. One-line summary + Args/Returns/Raises.

## Don'ts

- **Don't** use `print()` for user output — use `click.echo()` or `rich.print()`.
- **Don't** add backwards-compat shims for old mavis-* APIs without an issue.
- **Don't** introduce new top-level dependencies without updating `requirements.txt` + an issue.
- **Don't** hardcode model IDs — use `mavis.providers.registry.get_default_model()`.
- **Don't** write time-dependent logic (timestamps in code, not in tests).
- **Don't** catch bare `Exception` — catch the specific class and re-raise or log.
- **Don't** use `os.system()` — use `subprocess.run()` with `check=True`.
- **Don't** add comments like `# TODO: refactor this` — open an issue instead.

## Testing

- New tools MUST come with at least 3 unit tests in `tests/test_mavis_<name>.py`.
- Use `pytest` fixtures from `tests/conftest.py` (mocked env, vault, providers).
- Smoke test for executability: `python -c "import scripts.mavis_<name>"` and `chmod +x`.
- Run `make test` and `make lint` before pushing.

## Lint rules (enforced by pre-commit)

- `ruff check` — must pass with 0 errors
- `ruff format` — auto-format on commit
- `secrets` — no API keys, no tokens, no passwords
- `large files` — no files > 1MB

## Commit format

Conventional commits. Examples:

```
feat(rag): add BM25 hybrid search with RRF
fix(call): pass cache_ttl through to _openrouter_call
docs: update README with v10.0 architecture
chore(deps): bump anthropic-sdk to 0.45.0
refactor(providers): split into router + registry
test(cost): add cache hit rate assertion
```

## Tool description template (for new MCP tools)

```python
{
    "name": "mavis_<verb>_<noun>",
    "description": "<action>. <input prereq>. <output expectation>. <when to pick vs alternatives>. (200-400 chars)",
    "inputSchema": {  # flatten, top-level scalars preferred
        "type": "object",
        "properties": {
            "field1": {"type": "string", "description": "..."},
        },
    },
    "annotations": {  # MANDATORY 4 hints
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
}
```

## Provider usage rules

- Default LLM call → `mavis-providers call "..."` (auto-routes through chain)
- Sonnet 5 needed but rate-limited → use Haiku 4.5 or escalate to Opus 4.7
- For git commit review → `mavis-commit` (uses Copilot, Kimi K2.7 default)
- For cost tracking → `mavis-cost record ...` after every call
- For RAG → `mavis-rag "..."` (132 vectors, 88% precision@1)

## What to do when stuck

1. Read `prompts/SOUL.md` (identity)
2. Read `prompts/SYSTEM_PROMPT.md` (task)
3. Read `prompts/CONSTITUTION.md` (self-judgment)
4. Read `prompts/PROCESS_RULES.md` (enforcement map)
5. Search GitHub: `gh search code "your pattern" --owner anthropics --limit 5`
6. Search docs: `platform.claude.com/docs`, `docs.github.com`
7. Search RAG: `mavis-rag "your topic"`
8. If still stuck: spawn a sub-agent (Hermes for research, MaxClaw for code)

## Provenance

- Created 2026-08-05 during v10.0 ultra-research
- Pattern: GitHub Copilot custom instructions docs
- Sibling: `AGENTS.md` (cross-vendor standard)
