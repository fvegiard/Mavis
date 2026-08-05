# Mavis Process Rules — Enforcement Map

> The 10 standing orders (Francis's mandates), each paired with its
> **enforcement layer**. A rule that lives only in markdown is a wish.
> Pattern: AgentLint 2026 rule #3.

| # | Rule | Enforcement | Type |
|---|---|---|---|
| 1 | `ruff check` before claiming any Python file done | `.pre-commit-config.yaml` (ruff hook) + LSP | hard |
| 2 | Visual verification on rendered output (PDF/image/UI) | `mavis-hook` post-tool check (file is image/PDF → must have been read with vision) | hard |
| 3 | Reflexion v2: generate → critic (different model) → revise, max 2 rounds | `REFLEXION_LAYER.md` orchestrator | hard |
| 4 | Sandbox persistence: push to Supabase + copy to `/root/` | `mavis-package` script + daily cron | hard |
| 5 | Agent autonome mode: when Francis says go, GO | advisory (Francis's discretion) | soft |
| 6 | Never ask for new auth keys — use only what's in vault | `mavis-call` startup assert on vault presence | hard |
| 7 | Web/GitHub search BEFORE writing non-trivial code | `mini-coder-max` skill auto-invocation + `mavis-plan` step "search existing" | hard |
| 8 | Never trust model self-description (cross-check `platform.claude.com/docs`) | `mavis-rag-debug` skill for fact-check on model IDs | hard |
| 9 | Skill minimization: 23 dropped, 8 borderline (ask first) | `mavis-skill` allowlist config | hard |
| 10 | Prefix `🔴` for OAuth errors or fallback use | advisory (visibility rule, audit in `heuristics.log`) | soft |

## Categories

- **hard** = enforced by a hook, linter, CI check, or harness-level code
- **soft** = advisory only; Francis's discretion

## How to add a new rule

1. State the rule in one falsifiable sentence
2. Specify the enforcement layer (file + tool)
3. Mark it hard or soft
4. Add a row to the table above
5. Commit with `rules: add N — <name>`

## How to retire a rule

1. Mark `RETIRED — <date>: <reason>` in the table
2. Move to `prompts/PROCESS_RULES_RETIRED.md` after 30 days
3. Commit with `rules: retire N — <reason>`

## Provenance

- Compiled 2026-08-04 from 10 Francis mandates 2026-07-04 through 2026-08-05
- Enforcement map added 2026-08-05 (AgentLint rule #3)
- Pattern: AgentLint 2026 best practices (https://www.agentlint.app/blog/claude-md-best-practices-2026)
