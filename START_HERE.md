# Start Here

Read this first before doing non-trivial work in this workspace.

## Core Routes

1. For routine routing, read `docs/core/HERMES_ROUTER.md`.
2. For Hermes mode/state routing, read `docs/core/HERMES_RUNTIME_ROUTER.md`.
3. For Hermes vs Codex execution boundaries, read `docs/core/HERMES_EXECUTION_POLICY.md`.
4. For routine status/recall, read `_obsidian_vault/System/Assistant/Shared/Current State.md` first.
5. For deeper memory or recall, use `skills/obsidian-rag-check/SKILL.md` and follow `_obsidian_vault/Specs/Memory Query Protocol Spec.md`.
6. Treat the filesystem as a searchable space, not a folder tree to crawl. Use the standard search routes:
   - filename/path discovery: `scripts/search-files.ps1`
   - content search: `scripts/search-content.ps1`
   - file preview: `scripts/preview-file.ps1`
   - workspace/tooling snapshot: `scripts/inspect-workspace.ps1`
   - runtime manifest: `HERMES_SEARCHABLE_WORKSPACE` or `_runtime/searchable-workspace/manifest.json`, created by `scripts/enable-searchable-workspace.ps1`
7. Before destructive filesystem/git/path/junction/symlink operations, read `skills/dangerous-operation-guard/SKILL.md`.
8. For Telegram, use `scripts/send-telegram-home.ps1`; do not inspect secrets or use gateway fallback unless approved.
9. For new agents, use `AGENT_ONBOARDING.md` before assigning non-trivial work.
10. For session/shared memory, use `skills/session-close-memory/SKILL.md`. During work, add milestone events with `scripts/add-session-checkpoint.ps1`; after substantial work, flush them with `scripts/flush-session-checkpoints.ps1 -DryRun`, review for secrets/raw logs, then `-Apply` when clean. Do not wait for the user to ask or for session exit.
11. For the memory checkpoint flow explanation, read `docs/core/SESSION_CHECKPOINT_MEMORY.md`.

## Hard Rules

- Do not broad search unless the user explicitly approves.
- Do not use ad hoc recursive PowerShell for discovery when a standard search script can do it.
- Do not read or expose secrets, auth files, tokens, `.env`, or browser profiles.
- Do not store raw chat logs in Obsidian.
- Keep runtime state outside Obsidian unless it is summarized.
- Do not rely on chat context alone for future continuity. Meaningful milestones must be captured into `_runtime/session-checkpoints/` and flushed into the daily note and `System/Assistant/Shared/Current State.md` during the session, not only at final exit.
- Do not route code-heavy implementation/debugging/refactor/test work through Hermes as a model wrapper when direct Codex execution is available.
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
