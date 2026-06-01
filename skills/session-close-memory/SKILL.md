---
name: session-close-memory
description: Use at the end of substantial HermesGuildCore work sessions, after dry-run/test passes, or when the user asks to save/share session memory so future agents can resume without raw chat logs.
---

# Session Close Memory

Use the deterministic runtime routes first. The skill is only the procedure wrapper.

The route is configurable but bounded by `config/session-memory.json`.

## Workflow

1. During work, add small timestamped event checkpoints:

```powershell
.\scripts\add-session-checkpoint.ps1 -Kind code_change -Summary "fixed Notepad++ dry-run output" -MemoryValue medium
```

Use checkpoint events for meaningful milestones only:

- decision
- code change
- test pass/fail
- bug found/fixed
- user preference
- handoff/status point

Do not checkpoint raw terminal dumps, secrets, or ordinary "read file" noise.

2. Flush pending checkpoints with dry-run first:

```powershell
.\scripts\flush-session-checkpoints.ps1 -DryRun
```

3. Review the promoted candidate. It must contain distilled facts only:

- what changed
- what passed/failed
- next actions
- risks/guardrails
- dirty git snapshot

4. Apply immediately after substantial work when the dry-run candidate is clean. Also apply when the user explicitly asks to save/update memory or when closing a session:

```powershell
.\scripts\flush-session-checkpoints.ps1 -Apply
```

Use `close-session-memory.ps1` directly only for a one-off summary when no event queue exists.

## Rules

- Do not store raw chat logs.
- Do not include secrets, tokens, auth files, or terminal dumps.
- Do not mutate unrelated memory files.
- If writing through `_obsidian_vault` is blocked by sandbox permissions, request approval instead of bypassing the route.
- Do not leave only pending checkpoints or only a dry-run after substantial work unless the candidate contains a problem that must be fixed first.
- This route writes only allowlisted targets from `config/session-memory.json`, currently the daily note and `System/Assistant/Shared/Current State.md`.
- Do not loosen `allowed_writes` or `forbidden` patterns without explicit user approval.

## Current Design

This is a runtime-first memory system:

```text
session work -> add-session-checkpoint.ps1 -> _runtime/session-checkpoints
substantial slice -> flush-session-checkpoints.ps1 -> close-session-memory.ps1
-> Daily note + Shared Current State -> future agent startup/recall
```

The scripts are the stable contract. This skill tells agents when and how to call them.
