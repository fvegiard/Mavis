# Mavis Security Policy

> 5-layer defense model. 2026 consensus (OWASP GenAI June 2026, CSA Agentic
> MCP Best Practices, NSA/CISA June 2026). Source: 2026-08-05 ultra-research
> (security sub-agent) + `docs/security-hardening-2026.md` (deep dive).

## Threat landscape (2026)

- **30+ CVEs in 60 days** in MCP servers (43% command-injection)
- **OX Security April 2026** exposed 14 systemic CVEs in Anthropic's official
  MCP SDKs affecting ~200,000 servers
- **Claude Code CVEs (Francis's "laissée de côté")**: 11+ in 2025-2026
  (CVE-2025-59536, CVE-2026-21852, CVE-2026-25722-25725, CVE-2026-33068,
  CVE-2026-35020/21/22, CVE-2026-39861, CVE-2026-55607)
  - 2026-35020/21/22 still exploitable on Claude Code v2.1.91 as of 2026-04-03
- **OWASP MCP Top 10 (beta, April 2026)**: MCP01 token leakage through MCP10
  context injection

## 5-layer defense model (2026 consensus)

| Layer | Defense | Implementation |
|---|---|---|
| 1. Input sanitization | Strip Unicode tags, normalize whitespace, classify intent | `mavis-hook` pre-tool check |
| 2. Structural prompt separation | XML tags + stable prefix + cache_control | `prompts/SYSTEM_PROMPT.md` (XML contract) |
| 3. Output filtering | LLM-as-judge for high-stakes, regex for structural | `mavis-rag-eval` + `mavis-heuristics-daemon` |
| 4. Capability gating | Tool allowlist per sub-agent (Hermes / MaxClaw / Verifier) | `prompts/AGENTS.md` |
| 5. Continuous monitoring + kill switch | Circuit breaker, rate limit, audit log, abort on 3 fails | `mavis-call` circuit breaker + `heuristics.log` |

## 2026 secrets posture

- Model **never sees the secret**, ever
- Credential broker with short-lived scoped tokens (TTL 15-30 min)
- Replace `.env` files with broker + ephemeral tokens
- All API keys in vault, never in code

## Sandboxing spectrum (Levels 0-5)

| Level | Mechanism | Use case |
|---|---|---|
| 0 | No sandbox | Dev only |
| 1 | User permissions | Default |
| 2 | **seccomp-BPF + cap-drop ALL** | Mavis default |
| 3 | gVisor | Multi-tenant |
| 4 | Firecracker microVM | High-security |
| 5 | HW enclave (SGX) | Regulated |

**Mavis targets Level 2** minimum, Level 4 for multi-tenant.

## Hardening checklist (apply all)

- [x] OAuth 2.1 + PKCE for any remote MCP transport (drop DCR, use CIMD)
- [x] Pin exact package versions in `mavis-mcp.py` generated configs
- [x] Cryptographically sign tool descriptions (hash at registration, compare at session)
- [x] Read/write split: separate read-only vs write MCP servers
- [x] Audit log every tool call (agent, tool, args hash, idempotency key, result, duration)
- [x] Sandbox STDIO: no shell out from MCP tool
- [x] Cross-tenant namespace enforcement at storage layer
- [x] Session tokens ≤ 1h, refresh-token rotation, bound to IP/agent identity
- [x] TLS 1.3 baseline, mTLS between Mavis and remote MCP
- [x] Watch CVE feeds for `@modelcontextprotocol/*` packages

## CVE-aware dangerous patterns (in `mavis-hook.py`)

```python
DANGEROUS_PATTERNS = [
    r"curl[^|]*\|\s*bash",        # Pipe to shell
    r"eval\s*\(",                  # eval() in any code
    r"exec\s*\(",                  # exec() in any code
    r"base64.*decode",             # Base64 decode on stdin
    r"__import__",                 # Dynamic import
    r"subprocess.*shell=True",     # Shell injection
    r"\.env",                      # .env file access
    r"credentials\.json",          # credentials.json access
    r"AKIA[0-9A-Z]{16}",           # AWS key pattern
    r"sk-[a-zA-Z0-9]{32,}",        # OpenAI key pattern
    r"github_pat_[a-zA-Z0-9_]{22,}", # GitHub PAT pattern
]
```

## Reporting a vulnerability

- Open a private security advisory: https://github.com/fvegiard/Mavis/security/advisories/new
- Or email: francis.vegiard@protonmail.com (PGP key in `keys/`)
- Response SLA: 48h acknowledgement, 7d triage, 30d fix

## Provenance

- Compiled 2026-08-05 from OWASP GenAI June 2026, Check Point Feb 2026,
  OX Security Apr 2026, Anthropic CVD dashboard May 2026, CSA research notes
- Deep dive: `docs/security-hardening-2026.md` (~2,100 words, 50+ sources)
- Implementation: `mavis-hook.py` (pre/post tool validation)
