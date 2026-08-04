# Jarvis v2.0 — Architecture

## System diagram

```mermaid
flowchart TB
    subgraph USER["User (Francis)"]
        U1[Telegram @MavisAgentBot]
        U2[Claude.ai web]
        U3[Local Claude Code CLI]
    end

    subgraph CLOUD["Cloud Sandbox (this VM)"]
        direction TB
        subgraph MAVIS_AGENT["Mavis Agent (root session)"]
            M[System Prompt v3.0<br/>10-component Anthropic framework]
        end

        subgraph RAG["RAG Pipeline"]
            direction LR
            Q[Query] --> EMB[OpenRouter /embeddings<br/>text-embedding-3-small]
            EMB --> COS[Client-side cosine<br/>over 66 cached vectors]
            COS --> TOPK[Top-K chunks<br/>default 5, threshold 0.25]
            TOPK --> CTX[Build context block]
        end

        subgraph CALL["Claude API Wrapper"]
            direction TB
            SYS[System prompt array<br/>+ POOL_UNLOCK + cache_control]
            TOK[OAuth token<br/>ANTHROPIC_OAUTH_TOKEN]
            BETA[anthropic-beta header<br/>oauth-2025-04-20,claude-code-20250219]
            THK[thinking.type:disabled]
            RA[Retry-After + backoff<br/>+ circuit breaker]
            SYS --> API[Anthropic /v1/messages]
            TOK --> API
            BETA --> API
            THK --> API
            RA --> API
        end

        M --> RAG
        CTX --> SYS
        API --> ANS[Answer]
    end

    subgraph SUPA["Supabase (hzdzeleznvxzncgzqiub)"]
        direction TB
        MK[mavis_knowledge<br/>66 rows with embeddings]
        MT[mavis_tasks]
        MA[mavis_alerts]
        MS[mavis_state_snapshots]
        MC[mavis_cron]
    end

    subgraph OR["OpenRouter"]
        OE[OpenAI text-embedding-3-small]
    end

    U1 --> M
    U2 -.-> M
    U3 -.-> M

    COS <--> MK
    MAVIS_AGENT -.refresh.-> MT
    MAVIS_AGENT -.refresh.-> MA
    MAVIS_AGENT -.refresh.-> MS
    MAVIS_AGENT -.refresh.-> MC
    MT -.migrate.-> MK
    MA -.migrate.-> MK
    MS -.migrate.-> MK
    MC -.migrate.-> MK
    EMB --> OE

    ANS --> USER
```

## RAG pipeline (mavis-rag.py)

```mermaid
sequenceDiagram
    actor F as Francis
    participant RAG as mavis-rag.py
    participant OR as OpenRouter
    participant CC as client-side cache
    participant MC as mavis-call
    participant API as Anthropic

    F->>RAG: "Mavis orchestration architecture"
    RAG->>OR: POST /embeddings (text-embedding-3-small)
    OR-->>RAG: 1536-dim vector
    RAG->>CC: load mavis_knowledge (66 rows)
    RAG->>RAG: cosine similarity for each row
    RAG->>RAG: filter top-K above threshold
    RAG->>MC: system_prompt = base + "Contexte RAG" + chunks
    MC->>API: POST /v1/messages with pool-unlock + cache_control
    API-->>MC: 200 OK (or 429 → backoff → retry)
    MC-->>RAG: text response
    RAG-->>F: context-grounded answer
```

## Claude API wrapper state machine (mavis-call)

```mermaid
stateDiagram-v2
    [*] --> Ready
    Ready --> Calling: send request
    Calling --> Success: 200 OK
    Calling --> RateLimited: 429
    Calling --> Overloaded: 529
    Calling --> Error: 4xx/5xx

    RateLimited --> Parsing: read Retry-After
    Parsing --> Backoff: wait = Retry-After or backoff
    Backoff --> Calling: retry (up to 3)

    RateLimited --> CircuitOpen: retries exhausted
    CircuitOpen --> Ready: 5 min cooldown

    Overloaded --> Backoff: exp backoff
    Error --> [*]: return error
    Success --> [*]: return response
```

## Data flow

```
mavis_knowledge (Supabase, 66 rows)
  ↓
  text-embedding-3-small (1536 dim, OpenRouter)
  ↓
  embedding stored as TEXT (stringified JSON)
  ↓
  client-side cache (data/mavis_knowledge_cache.json, 1.3MB)
  ↓
  query-time: cosine top-K
  ↓
  inject into mavis-call system prompt
  ↓
  Haiku 4.5 / Sonnet 5 (OAuth pool unlock) → answer
```

## Cron jobs (active)

| Cron | Schedule | Purpose | task_id |
|---|---|---|---|
| `jarvis-rag-daily-refresh` | `0 4 * * *` (4am daily) | Re-embed NULL rows + migrate new + refresh cache | 426132459557092 |
| `supabase-unpause-detector` | `*/30 * * * *` | Polls DNS for project beagwczwcraeefxkkcmq (paused) | 420091670941895 |
| `tailscale-key-rotation-2026-09-25` | `0 9 26 9 *` (Sept 26 2026) | Reminder to rotate Tailscale auth key | 426215190323485 |

## Backup locations (3-redundant)

1. **Source**: `/workspace/jarvis/` (live, in this sandbox)
2. **Tarball**: `/workspace/jarvis-v1.0.tar.gz` + `/root/jarvis-v1.0.tar.gz` (survives sandbox restart partially)
3. **Supabase reference**: `mavis_knowledge` rows id=68 (v1) + id=85 (v2) — survives anything

## Files (final inventory)

```
/workspace/jarvis/
├── INSTALL.md                          # user-facing install guide
├── ARCHITECTURE.md                     # this file
├── scripts/
│   ├── mavis-call                      # Claude API wrapper v3 (8.9KB, lint-clean)
│   ├── mavis-rag.py                    # RAG wrapper (6.9KB)
│   ├── mavis-rag-eval.py               # eval 8 golden queries (7KB)
│   ├── mavis-vectorize.py              # OpenRouter embeddings (7.8KB)
│   └── mavis-vectorize-extra.py        # migrate 4 tables (8.5KB)
├── data/
│   └── mavis_knowledge_cache.json      # 66 rows, 1.3MB
├── prompts/
│   └── SYSTEM_PROMPT.md                # v3.0 10-component (8.1KB)
├── cron/
│   └── refresh-vectors.sh              # daily refresh
└── docs/
    └── ARCHITECTURE.md                 # this file
```

All scripts pass `ruff check` 0 errors. 8/8 golden queries retrieved (88% precision@1, 100% recall@5, MRR 0.938).
