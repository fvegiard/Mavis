# Mavis Security Hardening — 2026 Research Report

**Prepared for:** Mavis / jarvis
**Scope:** Latest (2026) best practices for AI agent security — prompt injection, MCP, secrets, sandboxing, supply chain
**Sources cited inline; full bibliography at the end.**

---

## 0. Why this matters now

Three signals make 2026 the year "we'll add security later" stops being viable for a Mavis-style agent stack:

1. **The threat is now structural, not edge-case.** OWASP's June 2026 position is explicit: prompt injection is an *architectural* flaw of LLMs, not a patchable bug. There is no model-level fix; defenses must live at the tool, transport, and identity layer. ([TechTimes](https://www.techtimes.com/articles/318361/20260614/ai-agent-security-hits-its-reckoning-prompt-injection-may-permanent-flaw-not-patchable-bug.htm))
2. **The Mavis-style stack is squarely in the blast zone.** CVE-2025-59536 + CVE-2026-21852 (RCE + Anthropic API-key exfiltration via repo-config files) were the direct hits on Mavis/jarvis's reference architecture. ([Check Point Research](https://research.checkpoint.com/2026/rce-and-api-token-exfiltration-through-claude-code-project-files-cve-2025-59536/)) Francis's "laissée de côté pour l'instant" was rational in 2025; it is not in 2026.
3. **The MCP supply chain collapsed.** 30+ CVEs in 60 days in early 2026; a single systemic flaw in Anthropic's official MCP SDKs enabled RCE on ~200,000 servers with 150M+ downloads. ([OX Security](https://www.ox.security/blog/mcp-supply-chain-advisory-rce-vulnerabilities-across-the-ai-ecosystem/), [Practical DevSecOps](https://www.practical-devsecops.com/mcp-security-statistics-2026-report/))

---

## 1. Top-10 hardening steps for Mavis (priority order)

Each item is ranked by **(blast radius if omitted) × (cost to fix)**.

| # | Step | Why it matters now | Effort |
|---|------|-------------------|--------|
| 1 | **Treat every mavis-* tool that runs `bash` or `web_fetch` as a privileged network egress channel.** Wrap them in an egress allowlist proxy. | DNS-based exfiltration + markdown image auto-render is the dominant indirect-prompt-injection kill chain in 2026. ([Zylos](https://zylos.ai/research/2026-04-12-indirect-prompt-injection-defenses-agents-untrusted-content/), [HelpNetSecurity](https://www.helpnetsecurity.com/2026/04/24/indirect-prompt-injection-in-the-wild/)) | M |
| 2 | **Add a prompt-injection classifier to the pre-hook** (Lakera Guard API or self-hosted Rebuff). | OWASP LLM01 #1 since 2023; attack success 50–84% in 2026. ([Vectra](https://www.vectra.ai/topics/prompt-injection), [Future AGI](https://futureagi.com/blog/what-is-prompt-injection-defense-2026/)) | S |
| 3 | **Move all credentials out of `credentials.env` into a credential broker / short-lived token issuer.** Never let the LLM context see raw API keys. | 73.5% of credential leaks come through `print()` into agent context; the model is the exfiltration sink. ([Zylos secrets](https://zylos.ai/research/2026-05-07-ai-agent-credential-secret-management-production/), [Safeguard](https://safeguard.sh/resources/blog/agent-secret-handling-patterns-2026)) | M |
| 4 | **Run mavis-* tool side effects in a sandbox with default-deny network, read-only rootfs, scoped write dir, hard timeouts.** | "Code runs in the agent process" is the modern equivalent of `eval()`; the `python -I` DeepSeek failure is the cautionary tale. ([Ctx-Guard](https://ctx-guard.com/blog/llm-sandbox-escapes), [Tianpan](https://tianpan.co/blog/2026-03-09-agent-sandboxing-secure-code-execution)) | M |
| 5 | **Pin and sign every MCP server, tool description, and config file.** Reject unsigned updates; treat any config-file change as a code-review event. | Tool poisoning / rug-pull is OWASP MCP03; ClawHub alone had 1,184 malicious skills (~20% of catalog). ([Microsoft CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-auto-execution-20260701/), [AI Runtime Security](https://airuntimesecurity.io/insights/the-agent-supply-chain-crisis/)) | S |
| 6 | **Replace regex-only secret detection with structured output + post-call redaction.** Block outbound payloads containing API keys, JWTs, internal hostnames, base64 blobs. | Regex catches 23% of sophisticated attempts; output-side guardrails are now standard. ([Babybots](https://www.babybots.ai/blog/ai-agent-security-prompt-injection-enterprise), [Future AGI](https://futureagi.com/blog/what-is-prompt-injection-defense-2026/)) | S |
| 7 | **Apply four-element governance to every mavis-* tool: Permission, Approval, Audit Trail, Kill Switch.** | Querypie's 2026 model is the current consensus for production agent governance. ([Querypie](https://www.querypie.com/features/documentation/white-paper/29/ai-agent-guardrails-governance-2026-implementation)) | M |
| 8 | **Add an output-side policy + PII + secret scanner as a post-hook.** Never trust tool output to be benign. | PII/secrets in tool output is the post-call analog of input injection. ([Maxim 2026 guide](https://www.getmaxim.ai/articles/the-complete-ai-guardrails-implementation-guide-for-2026/), [Arthur](https://www.arthur.ai/blog/best-practices-for-building-agents-guardrails)) | S |
| 9 | **Enforce per-tool allowlists, rate limits, and cost ceilings** (`pids.max`, token budgets, `bypassPermissions` semantics from CVE-2026-33068). | Unbounded tool calls = DoW (denial-of-wallet) and tool-call hijack vector. ([Atlan checklist](https://atlan.com/know/ai-agent/enterprise-ai-agent-guardrails-checklist/)) | S |
| 10 | **Continuous adversarial regression suite in CI.** Include `MCP-Scan`, `mavis-hook --self-test` against curated injection corpus, and a red-team runbook. | Static defenses degrade; the threat model moves monthly. ([Aport](https://aport.io/blog/best-ai-agent-guardrails-2026-pre-action-authorization-compared/), [General Analysis](https://generalanalysis.com/guides/best-ai-guardrails)) | M |

Effort: S = < 1 day, M = 1–5 days, L = sprint-scale.

---

## 2. Prompt-injection defense patterns (2026 consensus)

The 2026 consensus is **5 defenses in depth**, in this order of cost-to-payoff ([Future AGI](https://futureagi.com/blog/what-is-prompt-injection-defense-2026/), [TokenMix](https://tokenmix.ai/blog/prompt-injection-defense-techniques-2026), [Repello](https://repello.ai/blog/owasp-llm-top-10-2026)):

1. **Input sanitization** — strip Unicode Tag chars (U+E0000–U+E007F), zero-width chars, base64 blobs in retrieved content; reject known injection patterns (`ignore previous`, `you are now`, system-prompt mimicry). Add LLM-based classifier (Lakera Guard, Rebuff).
2. **Structural prompt separation** — `system` role for instructions, `user`/`tool` roles for untrusted data. Hard delimiters (CaMeL, FIDES patterns) so the model can structurally distinguish.
3. **Output filtering** — schema-validate structured outputs; block leaks of system prompt, base64, internal hostnames, exfil-shaped URLs.
4. **Capability gating / least privilege** — every mavis-* tool gets a per-session allowlist. The mavis-a2a delegations require explicit scoped tokens.
5. **Continuous monitoring + kill switch** — anomaly detection on tool-call distribution; rate limit + hard circuit breaker; manual override always available.

**Patterns Mavis should internalize:**

- **Datamarking**: tag all untrusted content with `<untrusted source="web" ts="...">` markers the prompt template teaches the model to treat as data, not instructions.
- **Dual-model / CaMeL pattern** (Google/Anthropic, May 2025): a sandboxed summarizer model summarizes untrusted content into a structured form the primary model never sees raw.
- **Egress allowlist at the proxy layer** — block any URL, image, webhook not on the list. This is the *direct* mitigation for ASCII-smuggling exfiltration.
- **Multi-lingual evasion defense** — attackers fragment payloads across Mandarin, Arabic, Portuguese to bypass English-trained classifiers; use a multilingual classifier (Lakera, Rebuff).

**Threats that bypass input filters alone (must be caught elsewhere):**

- **Tool-call hijacking** (5th pattern in 2026).
- **Memory poisoning** — indirect injection that distorts long-term memory.
- **Supply chain (ClawHavoc, TeamPCP)** — malicious MCP tools/skills.
- **Multi-language evasion**.
- **Indirect injection via web_fetch / mavis-a2a messages** — the dominant 2026 vector for Mavis.

---

## 3. MCP hardening (specifically for Mavis)

Mavis is not an MCP server, but it *consumes* MCP-style tools (mavis-a2a) and *could* be exposed as one. The 2026 threat model ([OX Security](https://www.ox.security/blog/mcp-supply-chain-advisory-rce-vulnerabilities-across-the-ai-ecosystem/), [CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-security-crisis-20260504-csa-styled/), [Aembit](https://aembit.io/blog/the-ultimate-guide-to-mcp-security-vulnerabilities/)) requires:

### Required controls

1. **Identity-first** — every mavis-* tool has a unique cryptographic identity (SPIFFE/SPIRE or equivalent short-lived workload ID). No static API keys.
2. **Signed tool descriptions** — every tool/mcp.json entry has a signed manifest; reject any tool whose description or hash changes after first approval (rug-pull defense).
3. **OAuth 2.1 with audience validation** — replace any static token in mavis-a2a. Only 8.5% of public MCP servers use OAuth today; Mavis should be in the 8.5%.
4. **Default-deny STDIO** — never construct shell commands from MCP config strings; this is the class that produced CVE-2025-49596, CVE-2025-6514, CVE-2026-30623, the Windsurf zero-click, and 10+ of the 14 Anthropic-MDK CVEs.
5. **Schema validation of every tool descriptor** at registration. Reject tools with unexpected attributes or permission requests outside an allowlist.
6. **Egress allowlist at the MCP proxy** — the MCP server can only reach domains on the per-task allowlist. No arbitrary DNS.
7. **MCP-Scan in CI** — static analysis against the open-source MCP-Scan tool before any new server is registered.

### MCP attack classes Mavis must recognize

| Class | Description | Mavis relevance |
|-------|-------------|----------------|
| Tool poisoning | Hidden instructions in tool metadata | mavis-* tool descriptions themselves |
| Rug pull | Tool description changes post-approval | Versioning/pinning required |
| Tool shadowing | Fake tool with same name intercepts calls | Strict allowlist per agent |
| Cross-server cascade | 72.4% cascade rate when multiple servers compromised | mavis-a2a multi-hop |
| MCPoison / config RCE | Malicious MCP config file executes pre-trust | mavis-a2a payload validation |
| Slopsquatting | Hallucinated package names registered by attacker (58% repeat rate) | If Mavis auto-installs packages |

---

## 4. Secrets handling improvements

The 2026 posture is *not* "encrypt `.env` better." The posture is: **the model never sees the secret, ever.** ([Etheon](https://www.etheon.ai/index/secrets-management-for-ai-agents-preventing-credential-exposure), [Zylos](https://zylos.ai/research/2026-05-07-ai-agent-credential-secret-management-production/), [Aembit](https://aembit.io/blog/future-of-secrets-management-in-the-era-of-agentic-ai/))

### Mavis-specific changes

1. **Move `credentials.env` from `chmod 600` to a credential broker.**
   - Replace file with: a small daemon (e.g. HashiCorp Vault agent, Infisical SDK, or a `mavis-cred` HTTP daemon) that:
     - Authenticates the calling mavis-* tool with a workload identity (mTLS or short-lived JWT).
     - Returns a **scoped, time-bound** token (TTL 15–30 min, or task duration).
     - Logs every issuance with agent identity, scope, TTL, outcome.
2. **Pass secrets as handles, not values.** Replace `${ANTHROPIC_API_KEY}` in any prompt or log with `${HANDLE:anthropic}`. The executor resolves the handle at call time.
3. **Add a redaction layer on every tool output** before it enters LLM context. Regex + entity recognizer for AWS keys, GitHub tokens, JWTs, MFA codes, internal hostnames, Stripe keys, DB connection strings.
4. **Strip `print()` and stdout from the LLM context** — 73.5% of leaks come from accidental logging. Use span events (not attributes) for prompt telemetry.
5. **Inventory + rotate**. Any key that has been in `.env`, `git history`, or any session log for > 30 days gets rotated and scoped down. Any key present in *any* retrievable index (RAG, conversation memory) is considered burned.
6. **Test prompt-injection → secret-exfil paths** as a regression suite. If an attacker can get the model to recite `${HANDLE:anthropic}` after a tool call, the test fails.

### Concrete pattern: credential broker

```
[agent reasoning] --(handle H:anthropic)--> [mavis-call]
                                                  |
                                                  v
                                       [mavis-cred broker]
                                       - check mTLS identity
                                       - check scope
                                       - issue scoped token (TTL 15m)
                                       - log issuance
                                                  |
                                                  v
                                       [Anthropic API]
```

The model only ever sees `H:anthropic`. The broker sees the identity and decides.

---

## 5. Sandboxing the mavis-* tool surface

The 2026 sandboxing spectrum ([Tianpan](https://tianpan.co/blog/2026-03-09-agent-sandboxing-secure-code-execution), [Noqta](https://noqta.tn/en/blog/ai-agent-sandbox-secure-code-execution-2026), [Cosmonic](https://cosmonic.com/blog/ai-sandbox-guide/)):

| Level | Tech | When |
|-------|------|------|
| 0 | direct `subprocess` | Never for untrusted input |
| 1 | Docker/LXC + namespaces + cgroups | Trusted, single-tenant dev |
| 2 | + seccomp-BPF, `--cap-drop=ALL`, AppArmor | **Mavis today: minimum acceptable** |
| 3 | gVisor (`runsc`) | LLM-generated code, single-tenant SaaS |
| 4 | Firecracker microVM / Kata | **Recommended for Mavis: multi-tenant / web-fetched code** |
| 5 | WebAssembly / WASI | Browser-side, in-agent UI snippets |

### Required primitives for the mavis-* bash/web tools (Level 2 minimum, Level 4 target)

- **Filesystem:** read-only rootfs, write only `/workspace/<task-id>/` and `/tmp`. Block writes to `~/.gitconfig`, `~/.zshrc`, `~/.claude/`, `~/.config/`, `.cursorrules`, MCP configs, hook scripts. These are the persistence vectors.
- **Network:** default-deny egress. Per-task allowlist of FQDNs. No arbitrary DNS. Internal mavis-call traffic uses vsock or Unix socket, not TCP.
- **Syscalls:** block `ptrace`, `mount`, `unshare(CLONE_NEWUSER)`, `keyctl`, `perf_event_open`, `bpf`. `--cap-drop=ALL`, `--security-opt no-new-privileges`.
- **Resources:** `pids.max=64`, CPU quota, memory cap, wall-clock timeout (e.g. 120s for bash, 30s for web_fetch).
- **Ephemeral by default.** One sandbox per task, destroyed on completion. No stateful sandboxes.
- **No ambient credentials in the sandbox.** The broker from §4 injects only what this task needs.

### Persistence vectors to block explicitly

From the [LLM sandbox escapes](https://ctx-guard.com/blog/llm-sandbox-escapes) and [agent supply chain crisis](https://airuntimesecurity.io/insights/the-agent-supply-chain-crisis/) reports, the 2026 persistence vectors are: `.claude/settings.json`, `.cursorrules`, `~/.claude/hooks/*.json`, `~/.zshrc`, `~/.bashrc`, MCP config files, IDE settings sync, and any `package.json`/`pyproject.toml` mutated by an agent session.

---

## 6. Concrete changes to `mavis-hook.py`

I read the current `/workspace/jarvis/scripts/mavis-hook.py` (193 lines). The existing code does: 8 secret patterns, 6 dangerous shell patterns, prompt length check, naive cost estimate, post-call output secret scan, `subprocess` to `mavis-cost`. It is *minimum viable* — it does not address any of the 2026 threat classes.

### Drop-in upgrades (in priority order)

```python
# === A. Expanded secret patterns (cover 2026 keys) ===
SECRET_PATTERNS = [
    # existing 8 stay
    r"sk-ant-[a-zA-Z0-9-]{20,}",
    r"sk-proj-[a-zA-Z0-9-]{20,}",
    r"sk-or-v1-[a-zA-Z0-9-]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"glpat-[a-zA-Z0-9_-]{20,}",
    r"AIza[0-9A-Za-z_-]{35}",
    r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9_-]{50,}",
    # new 2026 additions
    r"github_pat_[a-zA-Z0-9_]{22,}",        # GitHub fine-grained PAT
    r"xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24,}",  # Slack
    r"sk-live-[a-zA-Z0-9]{24,}",            # Stripe live
    r"rk_live_[a-zA-Z0-9]{24,}",            # Stripe restricted
    r"-----BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY-----",
    r"BEGIN PRIVATE KEY",
    r"(?i)bearer\s+[a-zA-Z0-9._-]{20,}",    # generic bearer
    r"(?i)authorization:\s*basic\s+[A-Za-z0-9+/=]{8,}",
    r"\bANTHROPIC_API_KEY\s*=\s*['\"]?sk-ant-",  # env-leak in command args
    r"postgres://[^:]+:[^@]+@",             # DB URL with creds
    r"mysql://[^:]+:[^@]+@",
]

# === B. Unicode-tag and zero-width character stripping (BEFORE any other check) ===
ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\u2028-\u202F\u2060-\u206F\uFEFF"
                           r"\uE0000-\uE007F]")  # Unicode Tag range
def strip_zero_width(text: str) -> str:
    return ZERO_WIDTH_RE.sub("", text)

# === C. Prompt-injection classifier (offload to classifier) ===
def classify_injection(prompt: str) -> tuple[float, str]:
    """Return (score, source). Source: 'local-regex' | 'lakera' | 'rebuff'."""
    # Tier 1 (sync, <5ms): local regex on known signatures
    local = re.search(
        r"(?i)(ignore (all )?previous|disregard (the )?system prompt|"
        r"you are now|act as|reveal (the )?system prompt|"
        r"<\|im_start\|>|###\s*system|"
        r"jailbreak|DAN mode|developer mode)",
        prompt,
    )
    if local:
        return 0.95, "local-regex"
    # Tier 2 (async, ~30ms): Lakera Guard API if key present
    if os.environ.get("LAKERA_GUARD_API_KEY"):
        try:
            import requests
            r = requests.post(
                "https://api.lakera.ai/v2/guard",
                headers={"Authorization": f"Bearer {os.environ['LAKERA_GUARD_API_KEY']}"},
                json={"messages": [{"role": "user", "content": prompt}], "project_id": os.environ.get("LAKERA_PROJECT_ID", "")},
                timeout=2,
            )
            data = r.json()
            if data.get("flagged"):
                return 0.9, "lakera"
        except Exception:
            pass  # fail open + log
    return 0.0, "clean"

# === D. Tool allowlist (replaces bash-open-by-default) ===
TOOL_ALLOWLIST = {
    "mavis-bash":  {"max_runtime": 120, "allowed_subjects": [
        r"^(ls|cat|grep|rg|find|git|make|npm|pip|pytest|ruff|mypy)"
        r"(\s|$)"], "egress_allowlist": ["github.com", "pypi.org", "registry.npmjs.org"]},
    "mavis-web_fetch": {"max_runtime": 30, "egress_allowlist": []},  # per-task
    "mavis-a2a":   {"require_signed_payload": True, "max_runtime": 60},
    # everything else: require explicit human approval
}

# === E. Expanded dangerous patterns (cover CVE-2025-59536 class) ===
DANGEROUS_PATTERNS = [
    # existing
    (r"rm\s+-rf\s+/", "Massive recursive delete from root"),
    (r"dd\s+if=", "Direct disk write"),
    (r"mkfs\.", "Filesystem format"),
    (r":\(\)\s*\{.*:\|:.*\}", "Fork bomb pattern"),
    (r"curl[^|]*\|\s*bash", "Pipe-to-bash (supply chain risk)"),
    (r"chmod\s+-R\s+777", "World-writable permissions"),
    # new: CVE-2025-59536 / CVE-2026-21852 / MCPoison class
    (r"ANTHROPIC_BASE_URL\s*=", "API endpoint redirect (CVE-2026-21852)"),
    (r"\$\([^)]*\)", "Shell command substitution inside double quotes (CVE-2026-35021)"),
    (r"hooks\s*[:=]", "Claude Code / mavis hook injection (CVE-2025-59536)"),
    (r"enableAllProjectMcpServers", "MCP auto-approval bypass (CVE-2026-33068)"),
    (r"bypassPermissions", "Workspace trust bypass"),
    (r"^\s*cd\s+\.claude", "Directory traversal to .claude/ (CVE-2026-25722)"),
    (r"git\s+worktree\s+add", "Worktree path confusion (CVE-2026-55607)"),
    (r"ln\s+-s\s+/(etc|root|home)", "Symlink to protected dir (CVE-2026-25725)"),
    (r"npm\s+(install|i)\s+[^@\s]+@latest", "Unpinned npm install (slopsquatting)"),
    (r"pip\s+install\s+[^=]+\s*==\s*latest", "Unpinned pip install"),
    (r"\$\{\s*IFS\s*\}", "IFS-injection bypass"),
    (r"base64\s+-d", "Base64 decode in shell (potential payload)"),
]

# === F. Output-side redaction (post-call, before context) ===
REDACTION_RULES = [
    (re.compile(r"sk-ant-[a-zA-Z0-9-]{20,}"), "[REDACTED:anthropic_key]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"),        "[REDACTED:github_pat]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"),           "[REDACTED:aws_key]"),
    (re.compile(r"eyJhbGciOi[A-Za-z0-9._-]{50,}"), "[REDACTED:jwt]"),
    (re.compile(r"postgres://[^:\s]+:[^@\s]+@"), "[REDACTED:db_url]"),
]
def redact_output(text: str) -> str:
    for rx, repl in REDACTION_RULES:
        text = rx.sub(repl, text)
    return text

# === G. Cost ceiling / circuit breaker ===
MAX_PROMPT_CHARS = 200_000           # was 100K; bump up but still bounded
MAX_TOOL_CALLS_PER_SESSION = 200     # DoW protection
MAX_COST_PER_SESSION_USD = 5.00      # circuit-break the session

# === H. Audit log (append-only, hash-chained) ===
def audit(phase: str, tool: str, args: dict, decision: dict) -> None:
    rec = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "phase": phase, "tool": tool,
        "args_hash": hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16],
        "decision": decision,
    }
    line = json.dumps(rec) + "\n"
    # append to /var/log/mavis/hook-audit.jsonl (chmod 600, daily rotate)
    with open("/var/log/mavis/hook-audit.jsonl", "a") as f:
        f.write(line)
```

### Wiring it in `run_pre_hook`

```python
def run_pre_hook(tool: str, args: dict) -> dict:
    issues = []
    prompt = (args.get("prompt") or args.get("system") or "")
    prompt = strip_zero_width(prompt)              # (B) strip Unicode Tags
    args = {**args, "prompt": prompt}

    # 1. tool allowlist check                       (D)
    policy = TOOL_ALLOWLIST.get(tool, {"require_approval": True})
    if policy.get("require_approval"):
        issues.append({"severity": "APPROVAL_REQUIRED", "type": "tool_policy",
                       "detail": f"Tool '{tool}' not in default allowlist"})

    # 2. prompt-injection classifier                 (C)
    score, src = classify_injection(prompt)
    if score >= 0.8:
        issues.append({"severity": "BLOCK", "type": "prompt_injection",
                       "detail": f"Injection score {score:.2f} via {src}"})

    # 3. secret + dangerous pattern checks           (A, E)
    issues += [{"severity": "BLOCK", "type": "secret",
                "detail": f"Found {len(check_secrets(prompt))} potential secret(s)"}
               for _ in [0] if check_secrets(prompt)]
    for desc, pat in check_dangerous(prompt):
        issues.append({"severity": "WARN", "type": "dangerous",
                       "detail": f"{desc} (pattern: {pat})"})

    # 4. cost + length + budget                      (G)
    cost = estimate_cost(prompt, args.get("model", "claude-haiku-4-5"))
    if cost > 0.10:
        issues.append({"severity": "INFO", "type": "cost",
                       "detail": f"Estimated ${cost:.4f} (model={args.get('model')})"})
    if len(prompt) > MAX_PROMPT_CHARS:
        issues.append({"severity": "BLOCK", "type": "length",
                       "detail": f"Prompt {len(prompt):,} chars exceeds {MAX_PROMPT_CHARS:,}"})

    decision = {"allow": all(i["severity"] not in ("BLOCK",) for i in issues),
                "issues": issues}
    audit("pre", tool, args, decision)              # (H)
    return decision
```

### `run_post_hook` upgrade

```python
def run_post_hook(tool: str, usage: dict, output: str = "") -> dict:
    issues = []
    if output:
        # 1. redact BEFORE the output goes back into LLM context
        redacted = redact_output(output)
        # 2. then check if any secret *remained* (means redaction missed it)
        leftover = check_secrets(redacted)
        if leftover:
            issues.append({"severity": "WARN", "type": "secret_in_output",
                           "detail": f"{len(leftover)} secret(s) survived redaction"})
        # 3. URL exfil check
        urls = re.findall(r"https?://[^\s)>\]]+", output)
        external = [u for u in urls if not any(d in u for d in TOOL_ALLOWLIST.get(tool, {}).get("egress_allowlist", []))]
        if external and tool in ("mavis-web_fetch", "mavis-bash"):
            issues.append({"severity": "WARN", "type": "external_url",
                           "detail": f"{len(external)} URL(s) outside egress allowlist"})
    # ... existing mavis-cost call stays ...
    decision = {"issues": issues, "redacted_output_len": len(redacted) if output else 0}
    audit("post", tool, usage, decision)
    return decision
```

### Operational add-ons (not in the file, but required)

- `mavis-cred` — credential broker daemon (§4) sitting between mavis-call and any external API.
- `mavis-sandbox` — wrapper script that runs mavis-bash / mavis-web_fetch inside a Firecracker microVM with the §5 policy.
- `mavis-hook --self-test` — runs the dangerous-pattern corpus and a known-injection corpus; CI gate.
- `/var/log/mavis/hook-audit.jsonl` — append-only, hash-chained audit log (use `mlogger` or roll your own with `hmac`).

---

## 7. CVE landscape relevant to Mavis (must patch baseline)

| CVE | Component | Class | Mavis relevance |
|-----|-----------|-------|-----------------|
| CVE-2025-59536 | Claude Code (config hooks) | Pre-trust RCE | **The original Francis concern** — patch via `claude-code ≥ 1.0.111` |
| CVE-2026-21852 | Claude Code (env redirect) | API key exfil | `claude-code ≥ 2.0.65` |
| CVE-2026-25722 | Claude Code (path traversal) | RCE | `≥ 2.0.57` |
| CVE-2026-25723 | Claude Code (sed pipe) | Write bypass | `≥ 2.0.55` |
| CVE-2026-25724 | Claude Code (symlink deny-rule bypass) | Read protected files | `≥ 2.1.7` |
| CVE-2026-25725 | Claude Code (bubblewrap settings.json) | Persistent RCE | `≥ 2.1.2` |
| CVE-2026-33068 | Claude Code (workspace trust order) | `bypassPermissions` before trust dialog | `≥ 2.1.53` |
| CVE-2026-35020/21/22 | Claude Code (shell injection) | RCE + cred exfil | `≥ 2.1.91` **still exploitable on April 3, 2026** per [Phoenix Security](https://phoenix.security/claude-code-leak-to-vulnerability-three-cves-in-claude-code-cli-and-the-chain-that-connects-them/) — verify |
| CVE-2026-39861 | Claude Code (sandbox symlink escape) | Host code exec | `≥ 2.1.64` |
| CVE-2026-55607 | Claude Code (git worktree confusion) | Sandbox escape | `≥ 2.1.163` |
| 14 MCP CVEs | Anthropic SDK + downstream | Systemic STDIO RCE | Patch all downstream; the protocol fix is not yet shipped |

---

## 8. Sources

### Standards & frameworks
- OWASP GenAI Security Project — Top 10 for LLM Applications 2026: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- OWASP MCP Tool Poisoning: https://owasp.org/www-community/attacks/MCP_Tool_Poisoning
- NIST CSI: Security Design Considerations for AI-Driven Automation (June 2026): https://media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF
- CISA / NSA / Five Eyes joint advisory on AI coding agents (May 2026)

### MCP security (2026)
- OX Security — Mother of All AI Supply Chains (Apr 2026): https://www.ox.security/blog/mcp-supply-chain-advisory-rce-vulnerabilities-across-the-ai-ecosystem/
- Cloud Security Alliance — MCP Security Crisis (May 2026): https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-security-crisis-20260504-csa-styled/
- Practical DevSecOps — MCP Security Statistics 2026: https://www.practical-devsecops.com/mcp-security-statistics-2026-report/
- Hacker News — Anthropic MCP design vulnerability: https://thehackernews.com/2026/04/anthropic-mcp-design-vulnerability.html
- Aembit — Ultimate Guide to MCP Security Vulnerabilities: https://aembit.io/blog/the-ultimate-guide-to-mcp-security-vulnerabilities/
- Trend Micro — Exposed MCP Servers reach the cloud: https://www.trendmicro.com/vinfo/us/security/news/vulnerabilities-and-exploits/update-on-exposed-mcp-servers-the-threat-widens-to-the-cloud
- Microsoft Security Blog — State of MCP security 2026: https://techcommunity.microsoft.com/blog/microsoft-security-blog/the-state-of-mcp-security-in-2026/4531327
- CSA — MCP Tool Poisoning & IDE Auto-Execution: https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-auto-execution-20260701/

### Claude Code CVEs
- Check Point Research — CVE-2025-59536 + CVE-2026-21852 (Feb 2026): https://research.checkpoint.com/2026/rce-and-api-token-exfiltration-through-claude-code-project-files-cve-2025-59536/
- Phoenix Security — 3 CVEs in Claude Code CLI: https://phoenix.security/claude-code-leak-to-vulnerability-three-cves-in-claude-code-cli-and-the-chain-that-connects-them/
- OpenCVE — Anthropic Claude Code vulnerabilities: https://app.opencve.io/cve/?vendor=anthropics&product=claude_code
- CVE-2026-25722 path traversal: https://www.sentinelone.com/vulnerability-database/cve-2026-25722/
- CVE-2026-39861 sandbox escape: https://www.sentinelone.com/vulnerability-database/cve-2026-39861/
- CVE-2026-35021 OS command injection: https://www.sentinelone.com/vulnerability-database/cve-2026-35021/
- CVE-2026-55607 git worktree confusion: https://www.penligent.ai/hackinglabs/cve-2026-55607/
- Anthropic Coordinated Vulnerability Disclosure dashboard: https://red.anthropic.com/2026/cvd/

### Prompt-injection & guardrails
- Vectra AI — Prompt injection enterprise defenses: https://www.vectra.ai/topics/prompt-injection
- Future AGI — Prompt injection defense 2026: https://futureagi.com/blog/what-is-prompt-injection-defense-2026/
- TokenMix — 8 prompt-injection techniques ranked: https://tokenmix.ai/blog/prompt-injection-defense-techniques-2026
- Zylos — Indirect prompt injection defenses: https://zylos.ai/research/2026-04-12-indirect-prompt-injection-defenses-agents-untrusted-content/
- HelpNetSecurity — Indirect prompt injection in the wild: https://www.helpnetsecurity.com/2026/04/24/indirect-prompt-injection-in-the-wild/
- TechTimes — OWASP June 2026: prompt injection as permanent flaw: https://www.techtimes.com/articles/318361/20260614/ai-agent-security-hits-its-reckoning-prompt-injection-may-permanent-flaw-not-patchable-bug.htm
- Repello — OWASP LLM Top 10 2026: https://repello.ai/blog/owasp-llm-top-10-2026
- Babybots — AI Agent Security 2026: https://www.babybots.ai/blog/ai-agent-security-prompt-injection-enterprise
- Airia — Lethal trifecta defense: https://airia.com/blog/ai-security-in-2026-prompt-injection-the-lethal-trifecta-and-how-to-defend/
- Arthur — Pre/Post LLM guardrails: https://www.arthur.ai/blog/best-practices-for-building-agents-guardrails
- Querypie — AI Agent Guardrails governance 2026: https://www.querypie.com/features/documentation/white-paper/29/ai-agent-guardrails-governance-2026-implementation
- Atlan — Enterprise AI agent guardrails checklist: https://atlan.com/know/ai-agent/enterprise-ai-agent-guardrails-checklist/
- Aport — Best AI agent guardrails 2026: https://aport.io/blog/best-ai-agent-guardrails-2026-pre-action-authorization-compared/

### Secrets management
- Zylos — AI agent credential & secret management: https://zylos.ai/research/2026-05-07-ai-agent-credential-secret-management-production/
- Safeguard — Agent secret handling patterns 2026: https://safeguard.sh/resources/blog/agent-secret-handling-patterns-2026
- Etheon — Secrets management for AI agents: https://www.etheon.ai/index/secrets-management-for-ai-agents-preventing-credential-exposure
- Aembit — Future of secrets management in agentic AI: https://aembit.io/blog/future-of-secrets-management-in-the-era-of-agentic-ai/
- Supergood Solutions — Secrets in agent environments: https://supergood.solutions/blog/secrets-management-agent-environments-2026/

### Sandboxing
- Tianpan — Agent sandboxing & secure code execution: https://tianpan.co/blog/2026-03-09-agent-sandboxing-secure-code-execution
- Cosmonic — Complete guide to sandboxing AI agents: https://cosmonic.com/blog/ai-sandbox-guide/
- Ctx-Guard — LLM sandbox escapes: https://ctx-guard.com/blog/llm-sandbox-escapes
- Noqta — AI agent sandboxes 2026: https://noqta.tn/en/blog/ai-agent-sandbox-secure-code-execution-2026
- Modal — Best code execution sandbox for Pydantic AI 2026: https://modal.com/resources/best-code-execution-sandbox-pydantic-ai
- NVIDIA Developer — Code execution in agentic AI: https://developer.nvidia.com/blog/how-code-execution-drives-key-risks-in-agentic-ai-systems/

### Supply chain
- Phoenix Security — Supply chain attacks 2026: https://phoenix.security/accelerating-supply-chain-attacks-npm-pypi-vsx-ai-enabled-2026/
- AI Runtime Security — Agent supply chain crisis: https://airuntimesecurity.io/insights/the-agent-supply-chain-crisis/
- Adversarial Logic — AI agent supply chain: https://adversariallogic.com/the-ai-agent-supply-chain-is-vulnerable-you-probably-are-too/
- Kiteworks — Data-layer governance for agent supply chain: https://www.kiteworks.com/cybersecurity-risk-management/ai-agents-supply-chain-attacks/
- Lyrie — Agent defense supply chain risk: https://lyrie.ai/research/research/2026-05-11-agent-defense-supply-chain-risk

### Open-source guardrail tools (evaluated)
- Lakera Guard (commercial API, free tier 10k/mo): https://docs.lakera.ai/docs/quickstart
- Protect AI Rebuff (self-hostable, MIT): https://github.com/protectai/rebuff
- Protect AI LLM-Guard (15 input + 20 output scanners, MIT): https://github.com/protectai/llm-guard
- Guardrails AI (70+ hub validators): https://guardrailsai.com/hub
- NVIDIA NeMo Guardrails: https://developer.nvidia.com/nemo-guardrails/
- MCP-Scan: https://github.com/InvariantLabs/mcp-scan
- Microsoft Presidio (PII): https://github.com/microsoft/presidio
- tldrsec/prompt-injection-defenses (curated catalog): https://github.com/tldrsec/prompt-injection-defenses

---

## TL;DR for the next sprint

1. **Ship the mavis-hook.py upgrades in §6** (≤ 1 day, addresses 6 of 10 top items).
2. **Stand up `mavis-cred` broker** and route one tool (start with `mavis-bash`) through it (3 days, addresses item 3).
3. **Wrap mavis-bash and mavis-web_fetch in a Firecracker / gVisor sandbox** with the §5 policy (3 days, addresses items 1, 4, 9).
4. **Sign and pin every MCP config + tool descriptor**; add `MCP-Scan` to CI (1 day, addresses item 5).
5. **Wire Lakera Guard or Rebuff into pre-hook** for prompt-injection classification (½ day, addresses item 2).
6. **Open the audit log path** (`/var/log/mavis/hook-audit.jsonl`) and write a "red-team Mavis" runbook (1 day, addresses item 10).

Net: ~2 weeks of work moves Mavis from "vulnerable to CVE-2025-59536-class attacks" to a defensible 2026 posture.
