# Session Checkpoint Memory

Purpose: preserve work continuity during a session without storing raw chat logs.

This route exists because Codex/Hermes cannot rely on a perfect session-exit hook. If the model context runs out, a tab closes, or the machine shuts down, unflushed chat context can be lost. The safer pattern is to record small milestone events during work and periodically flush only distilled events into shared Obsidian memory.

## Flow

```text
meaningful milestone
-> scripts/add-session-checkpoint.ps1
-> _runtime/session-checkpoints/*.json
-> scripts/flush-session-checkpoints.ps1 -DryRun
-> review promoted candidate
-> scripts/flush-session-checkpoints.ps1 -Apply
-> scripts/close-session-memory.ps1
-> Daily/YYYY-MM-DD.md + System/Assistant/Shared/Current State.md
```

## Event Shape

Each checkpoint event is a small JSON file under `_runtime/session-checkpoints/`.

Important fields:

- `local_time`: the human timestamp, such as `2026-06-01 09:36:25`
- `kind`: `decision`, `code_change`, `test`, `bug`, `audit`, `user_preference`, `status`, `handoff`, or `note`
- `memory_value`: `none`, `low`, `medium`, or `high`
- `summary`: one distilled sentence
- `evidence`: short command/result references, not terminal dumps
- `next_action`: follow-up tasks
- `risk`: guardrails or known risks
- `status`: `pending` until flushed, then `flushed`
- `promoted`: whether the event was written into shared memory

## Promotion Rule

By default, flush promotes only `medium` and `high` events.

Examples that should be promoted:

- architecture decision
- code change with verification
- test pass/fail that changes next action
- user preference or guardrail
- handoff/status checkpoint
- bug found/fixed

Examples that should stay low/noise:

- read a file
- typo in a command
- intermediate exploration with no decision
- duplicate status already captured

Use `-IncludeLow` only when intentionally preserving a low-value event for audit context.

## Examples

```powershell
.\scripts\add-session-checkpoint.ps1 `
  -Kind decision `
  -Summary "Use Guild Runtime contract-first; keep Flock as reference." `
  -MemoryValue high

.\scripts\add-session-checkpoint.ps1 `
  -Kind test `
  -Summary "Notepad++ dry-run returned created_file=false and would_create_file=true." `
  -Evidence "open-notepad-plus-plus.ps1 -DryRun -Json" `
  -MemoryValue medium

.\scripts\flush-session-checkpoints.ps1 -DryRun
.\scripts\flush-session-checkpoints.ps1 -Apply
```

## Guardrails

- Do not store raw chat logs.
- Do not store secrets, tokens, auth files, or full terminal dumps.
- Keep runtime events in `_runtime/session-checkpoints/` until promoted.
- Shared memory writes must stay routed through `close-session-memory.ps1`, which is bounded by `config/session-memory.json`.
- If writing through `_obsidian_vault` is blocked by sandbox permissions, request approval rather than silently leaving pending checkpoints.

