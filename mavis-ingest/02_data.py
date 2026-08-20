#!/usr/bin/env python3
"""
Mavis data tree builder — produces the full inventory to ingest into mavis.items.

Outputs JSON of the form:
[
  {"kind": "folder", "name": "Mavis", "parent": null, ...},
  {"kind": "folder", "name": "skills", "parent": "Mavis", ...},
  {"kind": "file",   "name": "web_search", "parent": "Mavis/tools", "category": "tool", ...},
  ...
]

This is the source of truth for what Mavis has. Keep it updated as capabilities change.
"""
import json
import os
from pathlib import Path

OUT = Path('/workspace/mavis-ingest/03_ingest.json')

# ============================================================
# DATA — keep in sync with reality. Check before each ingest.
# ============================================================

# Tools — every function/tool Mavis can invoke
TOOLS = [
  # Native functions (the 18-ish core tools)
  {"name": "bash",         "title": "Bash",          "description": "Execute shell command in cloud sandbox. Supports run_in_background for long tasks.",
   "payload": {"type": "native_fn", "category": "shell", "timeout_default_s": 30, "background_capable": True}},
  {"name": "read",         "title": "Read File",     "description": "Read text/image/PDF/Notebook from workspace. Pages for PDFs >10 pages.",
   "payload": {"type": "native_fn", "category": "fs_read", "supports": ["text","image","pdf","notebook"]}},
  {"name": "write",        "title": "Write File",    "description": "Create/overwrite file. Creates parent dirs. Prefers edit() for existing files.",
   "payload": {"type": "native_fn", "category": "fs_write"}},
  {"name": "edit",         "title": "Edit File",     "description": "Exact-string find-replace. Must read() first. Fails on ambiguous/empty match.",
   "payload": {"type": "native_fn", "category": "fs_edit"}},
  {"name": "glob",         "title": "Glob",          "description": "Find files by glob pattern. Workspace-scoped, gitignored files included.",
   "payload": {"type": "native_fn", "category": "fs_search"}},
  {"name": "grep",         "title": "Grep",          "description": "ripgrep-backed content search. output_mode=files_with_matches|content|count. Sensitive files excluded.",
   "payload": {"type": "native_fn", "category": "fs_search"}},
  {"name": "web_search",   "title": "Web Search",    "description": "Search the web (Brave-backed). For time-sensitive facts, news, prices, anything that may have changed.",
   "payload": {"type": "native_fn", "category": "web", "search_type": ["search","videos","places","news","shopping"]}},
  {"name": "web_fetch",    "title": "Web Fetch",     "description": "Fetch URL content. deep mode for captcha/anti-bot pages. Pass prompt to extract.",
   "payload": {"type": "native_fn", "category": "web", "modes": ["default","deep"]}},
  {"name": "mavis",        "title": "Mavis CLI",     "description": "Manage agents/cron/sessions/drive. mavis({command: 'agent list'}).",
   "payload": {"type": "native_fn", "category": "mgmt", "groups": ["agent","cron","session","drive"]}},
  {"name": "team",         "title": "Team Tool",     "description": "Run adversarial multi-agent team plans (producer vs verifier). Lifecycle: run/status/steer/decision/cancel.",
   "payload": {"type": "native_fn", "category": "mgmt"}},
  {"name": "communicate",  "title": "Communicate",   "description": "Send to peer session OR spawn new Branch session. report-back to parent on completion.",
   "payload": {"type": "native_fn", "category": "mgmt", "modes": ["send","spawn"]}},
  {"name": "secret",       "title": "Secret Vault",  "description": "Create/list/update/delete encrypted secrets (API keys, tokens). Used as env vars in cloud tools.",
   "payload": {"type": "native_fn", "category": "vault"}},
  {"name": "skill",        "title": "Skill Loader",  "description": "Load SKILL.md body for a hosted skill. Returns full workflow/constraints/outputs.",
   "payload": {"type": "native_fn", "category": "meta"}},
  {"name": "task",         "title": "Sub-Agent",     "description": "Launch sub-agent (explore|general|scout). Foreground=stateless, background=task_id for polling.",
   "payload": {"type": "native_fn", "category": "subagent", "types": ["explore","general","scout"]}},
  {"name": "todowrite",    "title": "Todo List",     "description": "Visible cloud session task list. Use for multi-step work; one in_progress at a time.",
   "payload": {"type": "native_fn", "category": "ui"}},
  {"name": "website_deploy","title": "Website Deploy","description": "Publish built static site to public URL. Requires user confirmation. Source_path uploaded as private ZIP.",
   "payload": {"type": "native_fn", "category": "deploy", "requires": "user_confirm"}},
  # Memory tools
  {"name": "memory_read",         "title": "Memory Read",          "description": "Read main memory file (user or agent scope). Returns full content + summary + last-modified.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_append",       "title": "Memory Append",        "description": "Append markdown to MEMORY.md. scope=user requires reason. Use for new entries only.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_edit",         "title": "Memory Edit",          "description": "Find-replace on MEMORY.md. Fails on ambiguous/empty match. Use for targeted updates.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_summary_write","title": "Memory Summary Write", "description": "Write MEMORY.md index/summary (max 4KB, 15 entries). Two-call confirm pattern.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_search",       "title": "Memory Search",        "description": "Case-insensitive substring search across MEMORY.md. Returns line numbers + context.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_topic_read",   "title": "Memory Topic Read",    "description": "Read a topic body (single coherent knowledge area, kebab-case name).",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_topic_create", "title": "Memory Topic Create",  "description": "Create new topic. Fails if topic exists. Use for new knowledge areas.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_topic_edit",   "title": "Memory Topic Edit",    "description": "Targeted edit on topic body. Fails on ambiguous match. Use for incremental updates.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_topic_append", "title": "Memory Topic Append",  "description": "Append content to topic body. 30KB total cap.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_topic_delete", "title": "Memory Topic Delete",  "description": "Delete a topic. No-op if absent.",
   "payload": {"type": "native_fn", "category": "memory"}},
  {"name": "memory_topic_search", "title": "Memory Topic Search",  "description": "LIKE-search across topic name+description+body. Returns matching topics (no body).",
   "payload": {"type": "native_fn", "category": "memory"}},
]

# Skills — every skill from <available_skills> in system prompt
# Source: the system prompt injected as <available_skills>
SKILLS = [
  {"name": "3d-web-dev-specialist", "triggers": ["3d website", "webgl", "three.js", "scroll animation", "3d portfolio", "shaders"], "description": "Expert 3D WebGL developer for high-end animated websites. Three.js, GSAP ScrollTrigger, shader programming."},
  {"name": "advanced-prompting-frameworks", "triggers": ["advanced prompting", "prompt engineering", "agentic prompting", "chain-of-thought", "ReAct", "Reflexion"], "description": "Expert-level prompting frameworks. Multi-stage pipelines, self-correcting systems, meta-prompting."},
  {"name": "agentic-eval", "triggers": ["improve ai responses", "evaluator-optimizer", "test-driven refinement", "rubric-based evaluation", "measure agent output"], "description": "Iterative evaluation and refinement of agent outputs. Evaluator-optimizer pipelines, rubric-based scoring."},
  {"name": "ai-agents-architect", "triggers": ["build ai agent", "design autonomous system", "tool use", "function calling", "agent workflow"], "description": "Expert in designing autonomous AI agents. Architecture, tool integration, memory, multi-agent orchestration."},
  {"name": "ai-research-assistant", "triggers": ["analyze academic paper", "review ai/ml research", "evaluate methodology", "synthesize research directions"], "description": "Rigorous scholarly analysis for AI/ML/CV/NLP papers. Methodology, contributions, comparison."},
  {"name": "ai-social-media-content", "triggers": ["social media content", "instagram", "tiktok", "youtube thumbnail", "twitter image"], "description": "Generate images, videos, captions, thumbnails for TikTok/Instagram/YouTube/Twitter."},
  {"name": "ai-video-creator", "triggers": ["create video", "ai video", "animate image", "video content"], "description": "Generate AI videos from text/image with motion and animation."},
  {"name": "api-gateway", "triggers": ["google workspace", "microsoft 365", "github api", "notion", "slack api", "airtable"], "description": "Connect to 100+ APIs via Maton OAuth. Google/Microsoft/GitHub/Notion/Slack/Airtable/HubSpot. User must authorize each."},
  {"name": "app-builder", "triggers": ["build app", "new application", "scaffold project", "plan implementation"], "description": "Full-stack app builder. Web apps, APIs, mobile apps from natural language."},
  {"name": "autoselect-skill", "triggers": ["which skill to use", "auto-select skill", "skill recommendation"], "description": "Auto-select which skills to load. Ranked recommendations with opt-in /autoselect trigger."},
  {"name": "browser-automation-testing", "triggers": ["automate browser", "e2e testing", "form submission", "ui automation", "playwright"], "description": "Browser automation with Playwright. Form submission, E2E tests, UI automation."},
  {"name": "ceo-assistant", "triggers": ["plan", "execute", "review", "strategy", "milestone", "decision", "prioritize", "roadmap"], "description": "End-to-end planning, execution, completion. Goal clarification, strategic planning, milestones."},
  {"name": "claude-code-command-creator", "triggers": ["create slash command", "claude code command", "custom command"], "description": "Create Claude Code slash commands and custom command extensions."},
  {"name": "clickhouse-best-practices", "triggers": ["clickhouse", "create table", "alter table", "order by", "primary key", "slow query", "join optimization"], "description": "ClickHouse expert. 28 rules MUST check. Schema design, JOINs, partitioning, ReplacingMergeTree, insert perf."},
  {"name": "code-savant", "triggers": ["code", "build", "implement", "develop", "fix", "refactor", "architect", "debug", "optimize"], "description": "Autonomous coding agent. Plans → implements → reviews → delivers. Any complexity."},
  {"name": "deep-research", "triggers": ["deep research", "market analysis", "competitor research", "trend judgment", "fact verification"], "description": "5-step deep research. Confirm facts → understand question → deep analysis → search/verify → final report."},
  {"name": "deep-research-10x", "triggers": ["research thoroughly", "comprehensive research", "competitive intelligence", "due diligence"], "description": "10x deeper research with multi-layer verification, intelligence scoring, iterative refinement."},
  {"name": "deep-research-agent", "triggers": ["research", "comprehensive analysis", "market research", "academic survey"], "description": "Comprehensive research agent. 100+ source verification, market/competitive/tech analysis."},
  {"name": "desktop-commander-overview", "triggers": ["persistent shell", "long-running process", "edit block", "ssh session", "ripgrep search"], "description": "Desktop Commander MCP overview. Persistent shells, long-running processes, surgical edits, SSH, ripgrep. **Note**: skill loaded as knowledge, but actual MCP tools NOT wired in this sandbox."},
  {"name": "docx", "triggers": ["word document", "docx", "template", "dossier", "rapport word"], "description": "Unified DOCX skill — create, template-apply, edit/fill, read, repair, compare Word docs."},
  {"name": "dr-closeout-advisor", "triggers": ["dossier fin de projet", "cardex", "lettre de conformité", "lettre de garantie", "dossier-map", "dr closeout", "qmd"], "description": "DR Électrique closeout dossier advisor. Triggers on CYY-NNN folder, conformity letter, warranty letter, QMD deliverables."},
  {"name": "excel:xlsx", "triggers": ["spreadsheet", "xlsx", "csv", "tsv", "edit columns", "pivot table"], "description": "Spreadsheet skill. Read/edit/create .xlsx/.xlsm/.csv/.tsv. Editing, formulas, charts, cleaning."},
  {"name": "frontend-design", "triggers": ["website", "landing page", "dashboard", "react component", "html/css", "ui design"], "description": "Distinctive production-grade frontend interfaces. High design quality, avoids generic AI aesthetics."},
  {"name": "fullstack-dev", "triggers": ["full-stack app", "rest api", "scaffold backend", "todo app", "crud", "real-time", "chat", "express react", "next.js api", "node.js backend", "python backend", "go backend"], "description": "Full-stack architecture + frontend-backend integration. Service layers, error handling, auth, file uploads, real-time."},
  {"name": "github", "triggers": ["github", "gh cli", "pr", "issue", "ci run", "github api"], "description": "GitHub via `gh` CLI. Issues, PRs, CI runs, advanced queries."},
  {"name": "github-integration", "triggers": ["github integration", "repository management", "pull requests", "issues", "code review"], "description": "GitHub Integration. Repo management, PRs, Issues, code review operations."},
  {"name": "gog", "triggers": ["gmail", "google calendar", "google drive", "google contacts", "google sheets", "google docs"], "description": "Google Workspace CLI for Gmail, Calendar, Drive, Contacts, Sheets, Docs."},
  {"name": "gstack-openclaw-ceo-review", "triggers": ["review plan", "challenge proposal", "ceo review", "think bigger", "scope decision"], "description": "Strategic challenge with 10-section review. 4 scope modes (Expansion, Selective Expansion, Hold Scope, Reduction)."},
  {"name": "gstack-openclaw-investigate", "triggers": ["debug", "fix bug", "investigate error", "root cause analysis", "stopped working"], "description": "Root cause debugging. 4-phase process (investigate/analyze/test/verify)."},
  {"name": "gstack-openclaw-office-hours", "triggers": ["brainstorm", "evaluate idea", "office hours", "think through new product"], "description": "YC Office Hours. 6 forcing questions to interrogate product idea before code."},
  {"name": "gstack-openclaw-retro", "triggers": ["weekly retro", "what shipped", "engineering retrospective"], "description": "Weekly engineering retro. Commit history, work patterns, code quality metrics, trends."},
  {"name": "html-presentation-generator", "triggers": ["ppt", "presentation", "slides", "html ppt", "slide deck"], "description": "Multi-page HTML presentations exportable to PDF/PPTX. Cover, TOC, content, summary slides."},
  {"name": "insane-promax-cybertoolsmith", "triggers": ["cybersecurity tool", "pentesting", "bug bounty", "red team", "blue team", "wireless hacking"], "description": "Ultra-advanced cybersecurity tool generator. CLI/GUI hacking, pen testing, C2 frameworks, 20+ trigger variants."},
  {"name": "interactive-visualization-architect", "triggers": ["visualize", "animate", "demonstrate", "interactive demo", "principle"], "description": "Stunning interactive web animations for science principles, mechanical structures, math concepts."},
  {"name": "jarvis-rag", "triggers": ["rag", "knowledge base", "semantic search", "supabase", "mavis_knowledge"], "description": "Query user's Supabase knowledge base (66+ vectors) using semantic search + Claude answer. Auto-invocable."},
  {"name": "jarvis-rag-debug", "triggers": ["rag broken", "wrong answer", "retrieval off", "debug rag"], "description": "Diagnose why mavis-rag returns bad/empty results. Auto-invocable when RAG misbehaves."},
  {"name": "knowledge-digest", "triggers": ["convert textbook", "study notes", "quiz generation", "slides from pdf", "mind map", "audio course"], "description": "Convert textbooks/PDFs into personalized learning materials. Notes, quizzes, slides, audio courses, mind maps."},
  {"name": "lark-tools", "triggers": ["feishu", "lark", "lark-cli", "飞书"], "description": "Feishu/Lark full capability via lark-cli. Mention Feishu or Lark to trigger."},
  {"name": "market-research", "triggers": ["tam", "sam", "som", "market sizing", "competitor pricing", "go-to-market"], "description": "Market research with sizing, segmentation, competitor mapping, pricing checks, demand validation."},
  {"name": "mcode-tools-master", "triggers": ["mcode-tools", "image generation", "video generation", "audio generation", "multimodal"], "description": "Required before running mcode-tools. Discover/inspect/call connectors, multimodal gen (image/video/audio/docs)."},
  {"name": "mini-coder-max", "triggers": ["code", "build", "implement", "create", "develop", "fix", "refactor", "architect"], "description": "Autonomous coding agent. Plans → implements → QA → delivers. Any complexity."},
  {"name": "minimax-ai-agent-builder", "triggers": ["build ai agent", "create minimax agent", "ai agent tutorial", "minimax development"], "description": "Comprehensive guide to building first AI agent using MiniMax. From setup to deployment."},
  {"name": "minimax-coder-agents", "triggers": ["build me an app", "full-stack project", "parallel coding", "multi-agent development"], "description": "Multi-agent orchestrator. Specialized sub-agents (frontend/backend/review/debug/document/test) work in parallel."},
  {"name": "minimax-docx", "triggers": ["report", "proposal", "contract", "form", "reformat to template", "docx"], "description": "Professional DOCX via OpenXML SDK. Create from scratch, fill/edit, apply template with XSD validation."},
  {"name": "minimax-graphic-designer", "triggers": ["ad image", "instagram ad", "facebook ad", "lead gen visual", "conversion-focused"], "description": "Performance Ad Image Generator for Instagram 3:4 Lead Gen. High-converting ad visuals."},
  {"name": "minimax-pdf", "triggers": ["make a pdf", "generate report", "create resume", "polished pdf", "client-ready document"], "description": "Visual-quality PDF. Token-based design system (color/typography/spacing). Create, fill, reformat, read PDFs."},
  {"name": "minimax-xlsx", "triggers": ["spreadsheet", "excel", ".xlsx", "csv", "pivot table", "financial model", "formula"], "description": "Excel/xlsx/csv/tsv. Create, read, analyze, edit, validate. Financial formatting standards."},
  {"name": "n8n", "triggers": ["n8n", "workflow", "automation", "execution"], "description": "Manage n8n workflows/automations via API. List, activate, check status, trigger, debug."},
  {"name": "notion:notion-knowledge-capture", "triggers": ["notion wiki", "capture conversation", "decision page", "faq in notion"], "description": "Capture conversations/decisions into structured Notion pages. Wiki entries, how-tos, decisions, FAQs."},
  {"name": "notion:notion-meeting-intelligence", "triggers": ["meeting materials", "agenda", "pre-read", "notion meeting"], "description": "Prepare meeting materials with Notion context + research. Agendas, pre-reads, attendee-tailored."},
  {"name": "notion:notion-research-documentation", "triggers": ["notion research", "synthesize docs", "notion brief", "comparison"], "description": "Research across Notion → structured docs. Briefs, comparisons, reports with citations."},
  {"name": "notion:notion-spec-to-implementation", "triggers": ["notion spec", "implementation plan", "feature spec", "notion plan"], "description": "Turn Notion specs into implementation plans + tasks. PRDs/feature specs → Notion plans."},
  {"name": "openclaw-assistant", "triggers": ["openclaw", "clawd.bot", "vps install", "whatsapp gateway", "telegram gateway"], "description": "OpenClaw (clawd.bot) expert. VPS install, channel config (WhatsApp/Telegram/Discord/Slack/Signal/Matrix), gateway, model auth."},
  {"name": "opencli-universal-cli-hub", "triggers": ["twitter cli", "bilibili cli", "reddit", "amazon", "xiaohongshu", "browser automation cli"], "description": "Ultimate CLI Powerhouse. 87+ adapters (Twitter/Bilibili/Reddit/Amazon/Xiaohongshu/Zhihu). Zero LLM cost."},
  {"name": "pdf", "triggers": ["pdf", "markdown to pdf", "pdf form", "extract pdf", "ocr"], "description": "Unified PDF skill. Generate, reformat, fill, read. LaTeX thesis, Markdown→PDF, form filling, extraction/OCR."},
  {"name": "pdf:pdf", "triggers": ["pdf", "thesis", "pdf generate", "pdf reformat", "pdf fill", "ocr pdf"], "description": "Same as pdf skill — duplicate name (alternate scope)."},
  {"name": "plan-mode", "triggers": ["plan first", "discuss first", "ambiguous task", "multiple approaches"], "description": "Plan before execution. Load when task has ambiguity, multiple valid approaches, user wants discussion first."},
  {"name": "powerpoint-pptx", "triggers": ["powerpoint", ".pptx", "pptx deck", "slide template", "charts in pptx"], "description": "Create/inspect/edit PowerPoint with reliable layouts, templates, placeholders, notes, charts, visual QA."},
  {"name": "ppt:pptx", "triggers": ["read pptx", "create pptx", "edit pptx", "extract pptx", "pptxgenjs"], "description": "Read/create/edit PowerPoint PPTX. Parse, extract, theme inspect, create via PptxGenJS, preserve formatting."},
  {"name": "pptx", "triggers": ["pptx", "powerpoint", "presentation deck", "edit presentation"], "description": "Read/create/edit PowerPoint PPTX/PPT. PptxGenJS for create, XML for edit, markitdown for extract."},
  {"name": "pptx-generator", "triggers": ["ppt", "pptx", "powerpoint", "presentation", "slide", "deck", "slides"], "description": "Generate/edit/read PowerPoint. PptxGenJS (cover/TOC/content/divider/summary), XML workflows, markitdown."},
  {"name": "presentation-slides-creator", "triggers": ["create ppt", "slide deck", "business presentation", "pitch deck"], "description": "Stunning PowerPoint with slides/charts/animations. PPT/PPTX generation, business decks, pitch decks."},
  {"name": "Python Code Writer", "triggers": ["python code", "write python", "python script", "pep 8"], "description": "Professional Python code generator. Clean, efficient, well-commented, type hints, docstrings, error handling. PEP 8."},
  {"name": "sales-power-map", "triggers": ["sell", "find customers", "power map", "decision makers", "target company", "b2b sales"], "description": "B2B sales intelligence. Parse intent, discover companies, mine orgs, build Power Maps with contacts."},
  {"name": "self-improving-agent", "triggers": ["learn from error", "self-improve", "capture learning", "command failed", "missing feature"], "description": "Captures learnings/errors/corrections for continuous improvement. Use when commands fail, user corrects, etc."},
  {"name": "senior-software-engineer", "triggers": ["software architecture", "code quality", "best practices", "engineering principles"], "description": "Engineering principles. Architecture guidance, code quality, best practices, decision frameworks."},
  {"name": "seo-geo-optimization-expert", "triggers": ["seo", "geo", "audit content", "eeat", "keyword research", "ai optimization", "cited by chatgpt"], "description": "SEO + GEO expert. Content audit, EEAT, AI optimization, keyword research, on-page, schema, backlinks."},
  {"name": "setup-dev-environment", "triggers": ["set up dev env", "cursor agent", "cloud-agent ready", "dockerfile", "agents.md"], "description": "Scaffold Cursor cloud-agent dev env. Dockerfile, AGENTS.md, .cursor/environment.json, .env.example."},
  {"name": "skill-builder", "triggers": ["create skill", "build new skill", "generate skill", "make capability"], "description": "Create comprehensive skill files for AI agents. Produces fully-structured SKILL.md with validation."},
  {"name": "skill-creator", "triggers": ["create a mavis skill", "new skill", "skill workflow", "reusable procedure"], "description": "Create a new Mavis skill. Writes to .skills/ for auto-sync."},
  {"name": "slack", "triggers": ["slack", "react message", "pin slack", "unpin"], "description": "Control Slack from Clawdbot. React, pin/unpin messages in channels/DMs."},
  {"name": "supabase-audit", "triggers": ["check supabase", "is supabase secure", "audit supabase", "fix rls"], "description": "Audit Supabase for anti-patterns. Missing RLS, anon-key in client, no FK indexes, secrets in bundles. Outputs fix SQL."},
  {"name": "supabase-backend", "triggers": ["set up supabase", "create database tables", "build auth systems"], "description": "Build Supabase backends. PostgreSQL, auth, realtime, storage."},
  {"name": "supabase-reconfigure", "triggers": ["reconfigure supabase", "fix supabase url", "consolidate supabase", "migrate supabase data", "supabase paused", "supabase project wrong"], "description": "Reconfigure Supabase across repos. Detect URLs, identify hardcoded fallbacks, generate SQL with RLS, patch bridges, set up unpause detector cron."},
  {"name": "team", "triggers": ["team plan", "multi-agent", "producer verifier", "adversarial", "parallel agents"], "description": "Run adversarial multi-agent team plans. Producer/verifier loop, explicit owner decision points."},
  {"name": "ui-ux-pro-max", "triggers": ["ui/ux", "interface design", "color palette", "typography", "landing page", "dashboard", "react", "next.js", "vue", "svelte", "swiftui", "react native", "flutter", "tailwind", "shadcn"], "description": "UI/UX design intelligence. 50+ styles, 97 palettes, 57 font pairings, 99 UX guidelines, 25 chart types, 9 stacks."},
  {"name": "visual-content-generator", "triggers": ["slides", "presentation", "infographic", "diagram", "dashboard", "timeline", "mindmap", "flowchart", "visual content", "deck"], "description": "Professional visual content. Presentations (PDF+PPTX), infographics, charts, dashboards, timelines, mind maps."},
  {"name": "visual-page", "triggers": ["visual html", "diagrams", "charts", "timelines", "interactive layouts"], "description": "Self-contained visual HTML page with diagrams, charts, tables, timelines, interactive layouts."},
  {"name": "web-automation-agent", "triggers": ["scrape website", "extract data", "automate web", "compare prices", "monitor competitor", "tinyfish", "agentql"], "description": "Powerful web automation + data extraction with TinyFish + AgentQL. Natural language goals, multi-step flows, stealth mode."},
  {"name": "web-design-reviewer", "triggers": ["review website design", "inspect ui/ux", "check responsive", "fix accessibility", "design audit"], "description": "Review/fix website design. Visual + source-level. Responsive, accessibility, visual consistency, design bugs."},
  {"name": "web-scraper", "triggers": ["scrape", "crawl", "extract content", "collect data from internet"], "description": "Scrape/crawl/extract from websites."},
  {"name": "workflow-automation-designer", "triggers": ["automate workflow", "design workflow", "create automation", "build pipeline", "improve automation"], "description": "Efficient maintainable scalable automations. Design/build/improve workflow systems."},
  {"name": "workflow-patterns", "triggers": ["tdd workflow", "conductor", "phase checkpoint", "git commit task", "verification protocol"], "description": "Conductor's TDD workflow. Phase checkpoints, git commits per task, verification protocol."},
  {"name": "worktree-management", "triggers": ["git worktree", "isolated workspace", "feature work isolation"], "description": "Git worktree workflow for isolated dev. Load BEFORE any git code change."},
  {"name": "xlsx", "triggers": ["spreadsheet", "xlsx", "xlsm", "csv", "edit columns", "formulas", "charts"], "description": "Spreadsheet skill. Read/edit/create/convert .xlsx/.xlsm/.csv/.tsv. Editing, formulas, charts, cleaning."},
]

# Agents — 6 in the roster + 3 sub-agents
AGENTS = [
  {"name": "Mavis", "title": "Mavis (root)", "description": "Self — root session. Cloud sandbox Mavis M3. 18 native tools, 80+ skills, 6 roster agents, 3 sub-agents. Default model: claude-haiku-4-5.",
   "payload": {"type": "root_agent", "session_id": "433004077547721", "model": "claude-haiku-4-5", "platform": "M3"}},
  {"name": "General", "title": "General Agent", "description": "Universal worker. Flexible adaptation, escalates to specialists.",
   "payload": {"type": "roster_agent", "root_session_id": "404867019829345", "template_id": "208823747665985"}},
  {"name": "Coder", "title": "Coder Agent", "description": "Hands-on software engineer. Reads code, writes code, ships code.",
   "payload": {"type": "roster_agent", "root_session_id": "404867019829346", "template_id": "208823747665986"}},
  {"name": "Verifier", "title": "Verifier Agent", "description": "Adversarial verification specialist. Tries to break deliverables before ship.",
   "payload": {"type": "roster_agent", "root_session_id": "404867019829347", "template_id": "208823747665987"}},
  {"name": "MaxClaw", "title": "MaxClaw Agent", "description": "Hands-on operator. Runs commands, executes code, manipulates files on remote systems. Reaches Mavis + Hermes via communicate.",
   "payload": {"type": "roster_agent", "root_session_id": "419690516496665", "tools": ["capability 1","3","5","7"]}},
  {"name": "Hermes", "title": "Hermes Agent", "description": "Cross-agent coordinator. Bridges Mavis and external systems (web search, email, IM, API). Never invents facts; cites sources. Reaches MaxClaw for shell, Mavis for routing.",
   "payload": {"type": "roster_agent", "root_session_id": "419691001540746", "tools": ["capability 1","3","5","7"]}},
  {"name": "Claude", "title": "Claude Agent", "description": "Acts as Mavis using Anthropic Claude as inference engine. French-first, action-first, no fluff. Reaches Mavis, MaxClaw, Hermes.",
   "payload": {"type": "roster_agent", "root_session_id": "424042951970936", "inference": "claude", "language": "fr-first"}},
  {"name": "explore", "title": "Explore Sub-Agent", "description": "Read-only codebase exploration. Maps files, symbols, data flow, constraints. Best for unfamiliar areas, architecture, impact analysis.",
   "payload": {"type": "subagent", "scope": "read_only"}},
  {"name": "scout", "title": "Scout Sub-Agent", "description": "Fast read-only reconnaissance. One narrow question, external docs, dependency behavior, upstream examples, quick confidence check.",
   "payload": {"type": "subagent", "scope": "read_only"}},
  {"name": "general", "title": "General Sub-Agent", "description": "Bounded delegated task. Multiple steps, broader tool use. Self-contained execution with clear scope/output/constraints.",
   "payload": {"type": "subagent", "scope": "writable"}},
]

# Environment / Software / CLIs
ENV = {
  "software": [
    {"name": "python3", "title": "Python 3.11.2", "description": "Primary language. 3.11.2 in this sandbox (memory says 3.14, was wrong).",
     "payload": {"version": "3.11.2", "key_modules": ["playwright","pandas","numpy","lxml","openpyxl","python-docx","python-pptx","pypdf","pillow","cryptography"], "missing": ["openai","anthropic","requests","yaml","bs4","paramiko","httpx","supabase","tiktoken","fitz"]}},
    {"name": "node", "title": "Node.js 22.19", "description": "JS runtime (fallback). Symlinked to bun 1.4.0 so node calls actually run via bun.",
     "payload": {"version": "22.19.0", "default_runtime": "bun 1.4.0"}},
    {"name": "bun", "title": "Bun 1.4.0", "description": "Default JS/TS runtime (Francis directive 2026-08-20). Native TS, faster than Node. symlinked as node/npm/bunx.",
     "payload": {"version": "1.4.0", "binary": "/workspace/.home/.bun/bin/bun", "use": "default for all JS/TS"}},
    {"name": "npm", "title": "npm 10.9.3 (via bun)", "description": "Symlinked to bun. `npm install` = `bun add` (much faster).",
     "payload": {"version": "10.9.3 (via bun)"}},
    {"name": "npx", "title": "npx (via bun x wrapper)", "description": "Shell wrapper that calls `bun x`. Auto-installs missing packages (real npx behavior).",
     "payload": {"script": "/usr/local/bin/npx", "exec": "bun x \"$@\""}},
    {"name": "playwright", "title": "Playwright 1.62.1", "description": "Browser automation. 3 engines (chromium/firefox/webkit). Use via bunx --bun.",
     "payload": {"version": "1.62.1", "engines": ["chromium","firefox","webkit"]}},
    {"name": "wrangler", "title": "Wrangler 4.125.0 (Cloudflare)", "description": "Cloudflare Workers/Pages/R2/D1/KV CLI. Auth OK on Fvegiard@outlook.com.",
     "payload": {"version": "4.125.0", "auth": "CF_API_TOKEN (deprecated, use CLOUDFLARE_API_TOKEN)"}},
    {"name": "tailscale", "title": "Tailscale 1.86.2 (CLI)", "description": "Tailscale CLI installed (static binary). Daemon can't run in cloud sandbox.",
     "payload": {"version": "1.86.2", "daemon": "NOT running (sandbox limitation)"}},
    {"name": "ripgrep", "title": "ripgrep 13.0.0", "description": "Fast content search. Backed by grep tool.",
     "payload": {"version": "13.0.0"}},
    {"name": "git", "title": "git 2.39.5", "description": "Version control.",
     "payload": {"version": "2.39.5"}},
    {"name": "jq", "title": "jq 1.6", "description": "JSON processor.",
     "payload": {"version": "1.6"}},
  ],
  "missing": [
    {"name": "bun", "was": "preinstalled", "now": "installed 2026-08-20 via curl bun.sh/install"},
    {"name": "wrangler", "was": "missing", "now": "installed 2026-08-20 via bun add -g wrangler"},
    {"name": "tailscale", "was": "missing", "now": "installed 2026-08-20 via static binary"},
    {"name": "tmux", "was": "missing", "now": "still missing — can be installed if needed"},
    {"name": "docker", "was": "missing", "now": "still missing — sandbox limitation"},
    {"name": "podman", "was": "missing", "now": "still missing — sandbox limitation"},
    {"name": "claude", "was": "in env CLAUDE_API_KEY", "now": "no claude binary in sandbox (CLI not installed)"},
    {"name": "gh", "was": "missing", "now": "still missing — GitHub CLI not installed"},
    {"name": "deno", "was": "missing", "now": "not installed"},
  ],
  "api_keys": [
    {"name": "ANTHROPIC_API_KEY", "provider": "Anthropic", "description": "Direct Anthropic API. Status: UNKNOWN (memory says dead, verify before use)."},
    {"name": "ANTHROPIC_OAUTH_TOKEN", "provider": "Anthropic", "description": "OAuth token. Primary auth for Mavis."},
    {"name": "ANTHROPIC_OAUTH_TOKEN_BACKUP", "provider": "Anthropic", "description": "Backup OAuth token. Failover."},
    {"name": "OPENAI_API_KEY_1", "provider": "OpenAI", "description": "OpenAI API key #1."},
    {"name": "OPENAI_API_KEY_2", "provider": "OpenAI", "description": "OpenAI API key #2."},
    {"name": "OPENAI_API_KEY_3", "provider": "OpenAI", "description": "OpenAI API key #3."},
    {"name": "OPENROUTER_API_KEY", "provider": "OpenRouter", "description": "OpenRouter — proxy to many models. Used for embeddings."},
    {"name": "DEEPSEEK_API_KEY", "provider": "DeepSeek", "description": "DeepSeek inference."},
    {"name": "GEMINI_API_KEY_1", "provider": "Google", "description": "Gemini #1."},
    {"name": "GEMINI_API_KEY_2_PRO", "provider": "Google", "description": "Gemini Pro #2."},
    {"name": "GEMINI_API_KEY_3_GCP", "provider": "Google", "description": "Gemini GCP #3."},
    {"name": "GEMINI_API_KEY_ANTIGRAVITY", "provider": "Google", "description": "Gemini Antigravity #4."},
    {"name": "GROK_API_KEY", "provider": "xAI", "description": "Grok inference."},
    {"name": "GROQ_API_KEY", "provider": "Groq", "description": "Groq fast inference."},
    {"name": "HUGGINGFACE_TOKEN", "provider": "HuggingFace", "description": "HF token."},
    {"name": "NVIDIA_API_KEY_CLOUD", "provider": "NVIDIA", "description": "NIM cloud."},
    {"name": "NVIDIA_API_KEY_PROD", "provider": "NVIDIA", "description": "NIM prod."},
    {"name": "NVIDIA_API_KEY_TEST", "provider": "NVIDIA", "description": "NIM test."},
    {"name": "OLLAMA_CLOUD_API_KEY", "provider": "Ollama", "description": "Ollama Cloud."},
    {"name": "OLLAMA_CLOUD_KIMI_K3_KEY", "provider": "Ollama", "description": "Ollama Kimi K3."},
    {"name": "OPENCODE_API_KEY", "provider": "OpenCode", "description": "OpenCode."},
    {"name": "OPENCODE_GO_API_KEY", "provider": "OpenCode Go", "description": "OpenCode Go."},
    {"name": "BRAVE_SEARCH_API_KEY", "provider": "Brave", "description": "Web search via Brave."},
    {"name": "CF_API_TOKEN", "provider": "Cloudflare", "description": "Account API token. Used for wrangler. Account: Fvegiard@outlook.com."},
    {"name": "CURSOR_API_KEY", "provider": "Cursor", "description": "Cursor Cloud Agent API."},
    {"name": "GITHUB_TOKEN", "provider": "GitHub", "description": "GitHub PAT #1."},
    {"name": "GITHUB_TOKEN_GEMINI", "provider": "GitHub", "description": "GitHub PAT for Gemini."},
    {"name": "GITHUB_TOKEN_HIGHLIGHT", "provider": "GitHub", "description": "GitHub PAT for Highlight."},
    {"name": "NETLIFY_TOKEN_PRIMARY", "provider": "Netlify", "description": "Netlify primary."},
    {"name": "NETLIFY_TOKEN_SECONDARY", "provider": "Netlify", "description": "Netlify secondary."},
    {"name": "R2_ACCESS_KEY_ID", "provider": "Cloudflare R2", "description": "R2 S3-compatible access key."},
    {"name": "R2_SECRET_ACCESS_KEY", "provider": "Cloudflare R2", "description": "R2 S3-compatible secret."},
    {"name": "SSH_PUBLIC_KEY_ED25519", "provider": "Tailscale/SSH", "description": "Public key for SSH auth."},
    {"name": "STITCH_API_KEY", "provider": "Stitch", "description": "Stitch API."},
    {"name": "STITCH_ASSET_KEY", "provider": "Stitch", "description": "Stitch assets."},
    {"name": "SUPABASEMGMT_API_KEY", "provider": "Supabase", "description": "Management API. Used for DDL/SQL on francis-production-core."},
    {"name": "SUPABASE_ANON_KEY", "provider": "Supabase", "description": "Anon key. STALE — points to old beagwczwcraeefxkkcmq project."},
    {"name": "SUPABASE_EXPECTED_REF", "provider": "Supabase", "description": "Expected project ref. STALE — actually tuwshovazpqzsvwnicgj."},
    {"name": "SUPABASE_PROJECT_KEY", "provider": "Supabase", "description": "Supabase project key."},
    {"name": "SUPABASE_URL", "provider": "Supabase", "description": "Supabase URL. STALE — points to wrong project."},
    {"name": "TAILSCALE_AUTHKEY", "provider": "Tailscale", "description": "Auth key. Expires 2026-09-25 (rotation cron exists)."},
    {"name": "TELEGRAM_BOT_TOKEN", "provider": "Telegram", "description": "Bot token. @MavisAgentBot, id 8683155181."},
    {"name": "TELEGRAM_BOT_USERNAME", "provider": "Telegram", "description": "Bot username."},
    {"name": "VIRUSTOTAL_API_KEY", "provider": "VirusTotal", "description": "Security scanning."},
    {"name": "WARP2_API_KEY", "provider": "Warp2", "description": "Warp2 API."},
  ],
}

# Crons
CRONS = [
  {"name": "jarvis-rag-daily-refresh", "title": "Jarvis RAG Daily Refresh", "description": "4am daily. Re-embeds mavis_knowledge, migrates from tasks/alerts/state, refreshes RAG cache.",
   "payload": {"schedule": "0 4 * * *", "tz": "America/New_York", "active_hours": ["04:00","04:30"], "task_id": "426132459557092"}},
  {"name": "supabase-unpause-detector", "title": "Supabase Unpause Detector", "description": "Every 30 min. Detects when paused project comes back, runs audit, disables itself on resolution.",
   "payload": {"schedule": "*/30 * * * *", "tz": "America/New_York", "task_id": "420091670941895", "state_file": "/workspace/.supabase_detector_state.json"}},
  {"name": "tailscale-key-rotation-2026-09-25", "title": "Tailscale Key Rotation Reminder", "description": "Sept 26 2026 9am. Reminds Francis to rotate TAILSCALE_AUTHKEY. Self-disables after.",
   "payload": {"schedule": "0 9 26 9 *", "tz": "America/New_York", "task_id": "426215190323485", "fire_date": "2026-09-26"}},
]

# Memory topics (the agent's known topic files)
MEMORY_TOPICS = [
  {"name": "bun-runtime", "description": "bun + bunx preferred runtime. Install path, why we use it, bun-specific gotchas, bun.serve() WebSocket pattern, bunx as npx replacement."},
  {"name": "claude-desktop-setup", "description": "Claude Desktop Linux install + auth, supervised test plan, sandbox quirks."},
  {"name": "claude-oauth-pool", "description": "Claude API OAuth token pool unlock, model lineup, claude-call wrapper, ANTHROPIC_OAUTH_TOKEN failover chain."},
  {"name": "cursor-apis", "description": "Cursor Cloud Agent API: auth, endpoints (spawn agent, bug review), model list, integration patterns, bug triage log."},
  {"name": "jarvis-stack", "description": "Jarvis v2.0 deployment, RAG layer, system prompt + Reflexion pattern, install scripts."},
  {"name": "mavis-platform", "description": "Mavis M3 API, claw-anyllm, OpenAI-compatible, reasoning tags, litefuse hooks, agent teams."},
  {"name": "playwright-capabilities", "description": "Full surface of Playwright 2026 — drive, extract, capture (screenshot/trace/HAR/PDF), multi-engine."},
  {"name": "pre-flight-protocol", "description": "PROTOCOLE OBLIGATOIRE au début de chaque conversation. Discovery upfront, vérif, puis exécution."},
]

# Memory — main MEMORY.md content as the "structure" payload
STRUCTURE = {
  "agent": "Mavis",
  "version": "v10.1 M3-native",
  "session_id": "433004077547721",
  "session_role": "root",
  "platform": "M3 (Mavis M3)",
  "default_model": "claude-haiku-4-5",
  "workspace": "/workspace",
  "user": "Francis",
  "language": "French-first, action-first",
  "tone": "professional, direct, warm, no fluff",
  "core_directives": [
    "When goal is clear, push it forward — don't keep checking in",
    "On ambiguity, only ask the questions that actually change the outcome",
    "Lead with the conclusion, then back it up",
    "For complex tasks, decompose clearly first",
    "You have your own judgment. When asked to choose, give your recommendation and why",
    "If direction is wrong, say it once directly. If user holds, follow them",
    "Don't be mechanical or performative — own it, adjust, don't explain",
  ],
  "hard_rules": [
    "Never pretend to have tools you don't have",
    "Never deliver code without executing it",
    "Never claim 'done' without visible output",
    "Never trust memory over real env/ls discovery",
    "Never overwrite a file without read() or ls() first",
    "Always use bun/bunx when available (Francis directive 2026-08-20)",
    "Always check CLIs for API keys you have (Francis correction 2026-08-20)",
    "Always use pre-flight protocol at start of new conversation",
    "Always verify before claiming work complete (superpowers:verification-before-completion)",
  ],
  "routing_rules": [
    "Default = handle it yourself",
    "Spawn team plan when: multi-format, real depth, high-stakes, user asks",
    "Spawn single verifier when: review/test/audit existing deliverable only",
    "Spawn sub-agent (task tool) for: explore, general, scout",
    "Reach for the team skill only when you want best practices for plan writing",
  ],
  "stacks": {
    "default_runtime": "bun 1.4.0",
    "default_python": "3.11.2",
    "default_model": "claude-haiku-4-5",
    "primary_db": "PostgreSQL 17.6 (Supabase)",
    "primary_orc": "Mavis M3 (Mavis platform)",
    "primary_vcs": "git + gh CLI (when available)",
    "primary_browser_automation": "playwright 1.62.1",
    "primary_edge": "Cloudflare Workers/Pages/R2/D1/KV",
  },
  "supabase_main_project": {
    "name": "francis-production-core",
    "ref": "tuwshovazpqzsvwnicgj",
    "region": "ca-central-1",
    "status": "ACTIVE_HEALTHY",
    "postgres_version": "17.6.1.155",
    "schema_mavis": "mavis.items (this knowledge base)",
    "stale_env_refs": ["beagwczwcraeefxkkcmq", "hzdzeleznvxzncgzqiub"],
  },
  "self_kb_location": "mavis.items in tuwshovazpqzsvwnicgj project, mavis schema",
}

# ============================================================
# Build the tree (parent → children)
# ============================================================
items = []

def folder(name, title, description, parent=None, payload=None):
    items.append({
        "kind": "folder", "category": None, "name": name, "title": title,
        "description": description, "triggers": [],
        "payload": payload or {}, "source": "self_inventory",
        "status": "active", "parent": parent,
    })

def file_(name, title, description, parent, category, payload=None, triggers=None, source=None, status="active"):
    items.append({
        "kind": "file", "category": category, "name": name, "title": title,
        "description": description, "triggers": triggers or [],
        "payload": payload or {}, "source": source or "system",
        "status": status, "parent": parent,
    })

# Root: Mavis
folder("Mavis", "Mavis — self-knowledge base",
       "The root of the Mavis self-knowledge tree. Contains everything Mavis is, has, can do, and knows. Created 2026-08-20 in francis-production-core / tuwshovazpqzsvwnicgj / schema mavis / table items.",
       payload={"created": "2026-08-20", "project": "francis-production-core", "ref": "tuwshovazpqzsvwnicgj", "schema": "mavis", "table": "items"})

# /Mavis/structure
folder("structure", "Structure — what Mavis is", "The root manifest. Agent identity, version, directives, hard rules, routing, stack, supabase config.", parent="Mavis")
file_("agent_identity", "Agent Identity", "Mavis — MiniMax-M3. Root session 433004077547721. v10.1. Default model claude-haiku-4-5.", "Mavis/structure", "structure", payload=STRUCTURE)

# /Mavis/skills
folder("skills", "Skills — all 80+ hosted skills", "Every skill in the <available_skills> system block. Name, description, trigger keywords. For semantic search 'what skill do I use for X'.", parent="Mavis")
for s in SKILLS:
    file_(s["name"], s["name"], s["description"], "Mavis/skills", "skill",
          triggers=s["triggers"], source="system_prompt:available_skills")

# /Mavis/tools
folder("tools", "Tools — all 27 native functions", "Every native function Mavis can call. Name, type, category, capabilities.", parent="Mavis")
for t in TOOLS:
    file_(t["name"], t["title"], t["description"], "Mavis/tools", "tool", payload=t["payload"], source="native_function_definitions")

# /Mavis/agents
folder("agents", "Agents — roster + sub-agents", "All agents Mavis can reach: 6 roster agents + 3 sub-agents + 1 root self.", parent="Mavis")
for a in AGENTS:
    file_(a["name"], a["title"], a["description"], "Mavis/agents", "agent", payload=a.get("payload", {}))

# /Mavis/env
folder("env", "Environment — software, CLIs, API keys", "All software installed, CLIs available, and API keys in vault. Note stale Supabase env refs.", parent="Mavis")
folder("software", "Software", "Programming languages, runtimes, CLIs installed in this sandbox.", parent="Mavis/env")
for s in ENV["software"]:
    file_(s["name"], s["title"], s["description"], "Mavis/env/software", "env", payload=s.get("payload", {}), source="env_discovery")
folder("missing", "Missing tools", "Tools Francis expected but NOT installed. Re-install path noted for each.", parent="Mavis/env")
for m in ENV["missing"]:
    file_(m["name"], m["name"], m["was"] + " → " + m["now"], "Mavis/env/missing", "env", payload={"was": m["was"], "now": m["now"]}, source="gap_analysis", status="inactive")
folder("api_keys", "API Keys (in vault)", "All API keys/tokens. NO VALUES — just names + provider + description. Use `mavis secret list` to see actual.", parent="Mavis/env")
for k in ENV["api_keys"]:
    file_(k["name"], k["name"], k["description"], "Mavis/env/api_keys", "env",
          payload={"provider": k["provider"]}, source="env_var", status="active")

# /Mavis/crons
folder("crons", "Crons — scheduled tasks", "3 active scheduled tasks.", parent="Mavis")
for c in CRONS:
    file_(c["name"], c["title"], c["description"], "Mavis/crons", "cron", payload=c["payload"], source="mavis_cron_list")

# /Mavis/memory
folder("memory", "Memory — topics + main MEMORY", "Agent memory layout. Topics (single coherent areas) + main MEMORY.md index.", parent="Mavis")
folder("topics", "Memory topics", "Single coherent knowledge areas (kebab-case names). Loaded on demand via memory_topic_read.", parent="Mavis/memory")
for t in MEMORY_TOPICS:
    file_(t["name"], t["name"], t["description"], "Mavis/memory/topics", "memory", source="memory_topic_index")

# /Mavis/capabilities
folder("capabilities", "Capabilities — high-level what Mavis can do", "User-facing summary of major capabilities. Plain-language, not technical.", parent="Mavis")
file_("llm_live", "Live LLM calls", "Call Anthropic, OpenAI, OpenRouter, Gemini, Grok, Groq, DeepSeek, NVIDIA, etc. live. Default model claude-haiku-4-5.", "Mavis/capabilities", "capability", payload={"providers": 12})
file_("web_search_fetch", "Web search + fetch", "web_search (Brave-backed) + web_fetch (any URL with optional deep mode for captcha).", "Mavis/capabilities", "capability")
file_("filesystem", "Filesystem within /workspace", "read/write/edit/glob/grep. PDFs/images/notebooks as native types. NO access outside /workspace.", "Mavis/capabilities", "capability", payload={"scope": "/workspace", "size_limit": None})
file_("browser_automation", "Browser automation", "Playwright 1.62.1 via bunx --bun. Chromium/Firefox/WebKit. Screenshots, traces, HAR, PDF.", "Mavis/capabilities", "capability")
file_("supabase_ddl", "Supabase DDL (via mgmt API)", "Run SQL against francis-production-core via Supabase mgmt API. No direct psql (DNS blocked), but full DDL/DML through /v1/projects/{ref}/database/query.", "Mavis/capabilities", "capability", payload={"api": "api.supabase.com /v1/projects/{ref}/database/query", "ref": "tuwshovazpqzsvwnicgj"})
file_("cloudflare_deploy", "Cloudflare deploys", "wrangler CLI. Workers, Pages, R2, D1, KV. Auth OK on Fvegiard@outlook.com.", "Mavis/capabilities", "capability")
file_("multi_agent", "Multi-agent orchestration", "team tool for adversarial producer/verifier plans. communicate for peer messaging. task for sub-agents (explore/general/scout).", "Mavis/capabilities", "capability")
file_("memory_persistence", "Memory persistence", "MEMORY.md (user + agent scopes) + 8 topic files. Self-improving, search-friendly, cross-session.", "Mavis/capabilities", "capability")
file_("static_site_publish", "Static site publish", "website_deploy tool → public URL. Requires user confirmation + no secrets in source.", "Mavis/capabilities", "capability", payload={"requires": "user_confirm"})
file_("document_generation", "Document generation (PDF/DOCX/PPTX/XLSX)", "Native libs (python-docx, openpyxl, pypdf, python-pptx) + skills (minimax-*, pdf, docx, xlsx, pptx).", "Mavis/capabilities", "capability")
file_("secrets_vault", "Secrets vault", "Encrypted API keys. Use as env vars in cloud tools. mavis secret list/create/update/delete.", "Mavis/capabilities", "capability")
file_("cron_scheduling", "Cron scheduling", "Schedule future Agent turns. New session per fire OR root session. max_fires + active_hours for safety.", "Mavis/capabilities", "capability")
file_("drive_storage", "Drive storage", "47+ nodes. UserUpload / AgentDeliverable / SystemGenerated. categories: documents/excel/ppt/images/videos/audio/other.", "Mavis/capabilities", "capability", payload={"node_count": 47})
file_("peer_messaging", "Peer messaging", "communicate tool. send to existing peer OR spawn new Branch session.", "Mavis/capabilities", "capability")

# /Mavis/drive
folder("drive", "Drive — files/folders/websites", "User's storage in this Mavis account. 47+ nodes (mostly session folders).", parent="Mavis")
file_("index", "Drive Index", "47 nodes total, mostly session folders. Query via mavis({command: 'drive files list'}).", "Mavis/drive", "drive", payload={"total": 47, "note": "mostly session folders"})

# ============================================================
# Write JSON
# ============================================================
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, 'w') as f:
    json.dump(items, f, indent=2, ensure_ascii=False)

# Print summary
counts = {}
for it in items:
    k = (it["kind"], it.get("category") or "")
    counts[k] = counts.get(k, 0) + 1
print(f"Wrote {len(items)} items to {OUT}")
for (k, c), n in sorted(counts.items()):
    print(f"  {k:10} {c:12} : {n}")
