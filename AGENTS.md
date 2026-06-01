# Workspace Agent Rules

This workspace is for building a local-first, memory-aware AI assistant around Hermes, Obsidian, and CLI workflow.

Read these files first when operating in this directory, when present:

- `START_HERE.md`
- `AGENT_ONBOARDING.md` when evaluating or introducing a new agent
- `PROJECT_CONTEXT.md`
- `TASKS.md`
- `HERMES_MAP.md`
- `docs/core/MEMORY_PIPELINE.md`
- `docs/core/HERMES_ROUTER.md`
- `docs/architecture/COGNITIVE_ARCHITECTURE.md`
- `docs/REPO_BOUNDARIES.md`
- `HERMES_USER_CONFIG.md` for private local activation preferences, when present; do not quote or expose secrets from it.
- `skills/dangerous-operation-guard/SKILL.md` before destructive filesystem/git/path/junction/memory/cron operations.
- `skills/obsidian-rag-check/SKILL.md` for cross-session recall, project memory lookup, or checking prior constraints before acting.

Operating rules:

- Prefer markdown-first workflow.
- Prefer small reversible steps.
- Do not recursively crawl the filesystem.
- Treat the filesystem as a searchable space, not a folder tree to crawl.
- Use `scripts/search-files.ps1` for bounded filename/path discovery. It tries Everything ES first and immediately falls back to scoped `fd`/PowerShell when ES or IPC is unavailable.
- Use `scripts/search-content.ps1` for bounded text search. It uses `rg` first and falls back to scoped PowerShell only when needed.
- Use `scripts/preview-file.ps1` for bounded file previews. It uses `bat` when available and falls back to `Get-Content -TotalCount`.
- Use `scripts/inspect-workspace.ps1` for a small tooling/top-level snapshot. It uses `eza` when available.
- Treat `zoxide` as human navigation state only; agents should not depend on it for automation.
- Do not use ad hoc recursive PowerShell discovery when a standard search script exists.
- If file discovery still fails, use shallow known-path inspection only.
- Avoid `node_modules`, virtual environments, caches, and generated folders unless explicitly needed.
- Do not read or expose secrets from `.env`, auth files, tokens, or browser profiles.
- Do not write raw chat logs into Obsidian.
- Distill memory before storing it.
- After meaningful milestones during work, run `scripts/add-session-checkpoint.ps1` with a short distilled event such as `09:24 fixed X` / `test Y passed` / `decision Z`. Store only event summaries, evidence, next action, and risks. After substantial work, run `scripts/flush-session-checkpoints.ps1 -DryRun`, review the promoted candidate for secrets/raw logs, then run `scripts/flush-session-checkpoints.ps1 -Apply` immediately when clean. This is the workspace automatic shared-memory route; do not wait for the user to ask again or for session exit.
- Keep runtime state outside Obsidian unless it has been summarized.
- Treat memory as semantic compression, not raw storage.
- Ask before enabling delegation, MoA, worktrees, destructive commands, or broad search.
- Before any destructive or path-sensitive operation, use `skills/dangerous-operation-guard/SKILL.md`; inspect `LinkType`, `Target`, and `Attributes` before removing or renaming Windows paths.
- For routine requests, consult `docs/core/HERMES_ROUTER.md` and use known routes directly.
- Do not route code-heavy implementation/debugging/refactor/test work through Hermes as a model wrapper when direct Codex execution is available. Hermes should act as router, memory, planner, reviewer, and secretary; Codex/direct workers should do repo surgery.
- For recall/memory questions or when prior constraints matter, use `skills/obsidian-rag-check/SKILL.md` and search Obsidian FTS before relying on hot memory.
- For non-trivial memory lookup, follow `_obsidian_vault/Specs/Memory Query Protocol Spec.md`: classify the request, use a query packet, search source tiers in order, and treat session-history fallback as a repair signal.
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
- Session checkpoint events live under `_runtime/session-checkpoints/` until flushed. Shared memory writes are bounded by `config/session-memory.json`; only the allowlisted daily note and `System/Assistant/Shared/Current State.md` may be written. Never store raw logs or secrets. If `_obsidian_vault` write is sandbox-blocked, request approval rather than silently leaving only a dry-run.
