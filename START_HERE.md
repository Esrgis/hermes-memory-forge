# Start Here

Read this first before doing non-trivial work in this workspace.

## Core Routes

1. For routine routing, read `docs/core/HERMES_ROUTER.md`.
2. For routine status/recall, read `_obsidian_vault/System/Assistant/Shared/Current State.md` first.
3. For deeper memory or recall, use `skills/obsidian-rag-check/SKILL.md` and follow `_obsidian_vault/Specs/Memory Query Protocol Spec.md`.
4. For filename/path discovery, use `scripts/search-files.ps1`. It tries Everything ES first, then falls back to scoped `fd` or PowerShell.
5. Before destructive filesystem/git/path/junction/symlink operations, read `skills/dangerous-operation-guard/SKILL.md`.
6. For Telegram, use `scripts/send-telegram-home.ps1`; do not inspect secrets or use gateway fallback unless approved.
7. For new agents, use `AGENT_ONBOARDING.md` before assigning non-trivial work.

## Hard Rules

- Do not broad search unless the user explicitly approves.
- Do not read or expose secrets, auth files, tokens, `.env`, or browser profiles.
- Do not store raw chat logs in Obsidian.
- Keep runtime state outside Obsidian unless it is summarized.
- If evidence is missing, do not guess. Search the right source tier or ask.
- If a task is too hard for the current model, write a deferred-analysis note with evidence and next action, then stop.

## Mental Model

```text
Obsidian = durable semantic memory
SQLite/_runtime = live runtime state and current-state source of truth
Hermes memory = compact hot pointers
scripts = deterministic routes
skills = required procedures
```
