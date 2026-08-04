# Mavis — Quantum Agentic Orchestrator

> Autonomous AI agent system by Mavis, for Francis Végiard. 16 production tools, 5 LLM providers, 66 RAG vectors.

## What is Mavis?

Mavis is a **quantum agentic** orchestrator — a self-improving AI agent that:
- Routes every request to the right tool / model / agent
- Operates with full agency (no confirmation needed)
- Maintains perfect context across files, memory, and knowledge base
- Validates everything against Anthropic official docs
- Persists across sandbox restarts (workspace + /root/ + Supabase)

## Stack (v7.0, 2026-08-04)

### 16 mavis-* tools

| Tool | Purpose |
|---|---|
| `mavis-call` | Claude API wrapper (OAuth pool unlock + Retry-After + circuit breaker + cache_control) |
| `mavis-rag` | RAG retrieval over 66 Supabase vectors (88% precision@1, 100% recall@5) |
| `mavis-rag-eval` | 8 golden queries for retrieval quality |
| `mavis-vectorize` | OpenRouter embeddings (text-embedding-3-small, 1536 dim) |
| `mavis-vectorize-extra` | Migrate 4 tables into mavis_knowledge |
| `mavis-stream` | SSE streaming output |
| `mavis-plan` | Plan-then-execute orchestrator |
| `mavis-skill` | Skill auto-loader (keyword ranking) |
| `mavis-cost` | Cost analytics with per-model pricing |
| `mavis-hook` | Pre/post-call validation (secrets, dangerous ops, cost warn) |
| `mavis-browser` | Playwright automation (chromium) |
| `mavis-mcp` | MCP server creator (wraps any mavis tool as MCP) |
| `mavis-worktree` | Git worktree workflow |
| `mavis-a2a` | Agent-to-Agent protocol (Supabase-backed) |
| `mavis-providers` | Multi-LLM router (7 providers) |
| `mavis-commit` | Git commit + Copilot code review |

### 5 working LLM providers

| Provider | Priority | Latency | Cost | Use case |
|---|---|---|---|---|
| `openrouter-free` | 0 | 620-800ms | **FREE** | Default for cheap queries |
| `claude-oauth` | 1 | 970-1190ms | paid | Premium direct (Fable 5) |
| `copilot` | 2 | 780-940ms | paid | **RESERVED for commit/review** |
| `groq` | 3 | 230-280ms | paid | Fastest fallback |
| `openrouter` | 4 | 700-900ms | paid | Variety fallback |

### Free models (7 confirmed)

- **Long context (1M)**: `nvidia/nemotron-3-ultra-550b-a55b:free`
- **Reasoning**: `nvidia/nemotron-3-super-120b-a12b:free` (262K)
- **Google quality**: `google/gemma-4-31b-it:free` (262K) or `gemma-4-26b-a4b-it:free` (131K)
- **Fast + small**: `inclusionai/ling-3.0-flash:free` (262K)
- **Code**: `cohere/north-mini-code:free` (256K)
- **Lightweight**: `nvidia/nemotron-nano-9b-v2:free` (128K)

### 3 active crons

- `jarvis-rag-daily-refresh` (4am daily) — refresh embeddings
- `supabase-unpause-detector` (*/30) — detect when paused Supabase project comes back
- `tailscale-key-rotation-2026-09-25` (Sept 26) — rotate Tailscale auth key

## Quick start

```bash
# Run the install script (Debian / MX Linux)
bash install-mxlinux.sh --oauth-token sk-ant-...

# Or use directly
export OPENROUTER_API_KEY=sk-or-v1-...
export ANTHROPIC_OAUTH_TOKEN=sk-ant-...
export GITHUB_COPILOT_OAUTH=ghu_...

mavis-rag "How does Mavis work?"
mavis-providers test
mavis-commit
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Mavis v7.0                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User ──> Telegram (MavisBot)                              │
│              │                                             │
│              ▼                                             │
│  ┌─────────────────┐    ┌──────────────────────────────┐  │
│  │  mavis-rag      │───>│ Supabase mavis_knowledge     │  │
│  │  (RAG retrieve) │    │ (66 vectors, 1536 dim)       │  │
│  └─────────────────┘    └──────────────────────────────┘  │
│              │                                             │
│              ▼                                             │
│  ┌─────────────────┐    ┌──────────────────────────────┐  │
│  │  mavis-providers│───>│ openrouter-free (default)    │  │
│  │  (router)       │    │ claude-oauth (Fable 5)       │  │
│  └─────────────────┘    │ copilot (commit/review only) │  │
│              │           │ groq (fast)                  │  │
│              ▼           │ openrouter (variety)         │  │
│  ┌─────────────────┐    └──────────────────────────────┘  │
│  │  mavis-call     │                                       │
│  │  (Claude API)   │                                       │
│  └─────────────────┘                                       │
│              │                                             │
│              ▼                                             │
│  User response + memory write + cost tracking              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## License

MIT — Mavis quantum agentic, 2026-08-04.

## Contact

Built by Mavis (MavisAgentBot) for Francis Végiard (`@fvegiard`).
Telegram: `@MavisAgentBot` | `MaxHermes` (research) | `MaxClaw` (code/infra).
