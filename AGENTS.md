# Workspace Agent Rules

This workspace is for building a local-first, memory-aware AI assistant around Hermes, Obsidian, and CLI workflow.

Read these files first when operating in this directory, when present:

- `PROJECT_CONTEXT.md`
- `TASKS.md`
- `HERMES_MAP.md`
- `docs/core/MEMORY_PIPELINE.md`
- `docs/core/HERMES_ROUTER.md`
- `docs/architecture/COGNITIVE_ARCHITECTURE.md`
- `docs/REPO_BOUNDARIES.md`
- `HERMES_USER_CONFIG.md` for private local activation preferences, when present; do not quote or expose secrets from it.

Operating rules:

- Prefer markdown-first workflow.
- Prefer small reversible steps.
- Do not recursively crawl the filesystem.
- Use Everything ES for bounded discovery when it is running.
- If Everything ES is not available, use shallow known-path inspection only.
- Avoid `node_modules`, virtual environments, caches, and generated folders unless explicitly needed.
- Do not read or expose secrets from `.env`, auth files, tokens, or browser profiles.
- Do not write raw chat logs into Obsidian.
- Distill memory before storing it.
- Keep runtime state outside Obsidian unless it has been summarized.
- Treat memory as semantic compression, not raw storage.
- Ask before enabling delegation, MoA, worktrees, destructive commands, or broad search.
- For routine requests, consult `docs/core/HERMES_ROUTER.md` and use known routes directly.
- Do not load broad skills or inspect databases for simple messaging, greetings, note routing, or status checks.
- For Telegram requests, use `scripts/send-telegram-home.ps1`; do not use cron or gateway fallback without explicit approval.

Provider policy:

- Treat paid or quota-limited providers as scarce.
- Use the configured daily provider for routine work.
- Use the configured coding provider for code-heavy work.
- Avoid spawning sub-agents unless the user explicitly asks.
- Keep a fallback/manual low-cost provider when available.

Obsidian boundary:

- Obsidian vault is long-term knowledge.
- Hermes built-in memory is distilled assistant memory.
- `_runtime/` is scratch/runtime state for this workspace.
