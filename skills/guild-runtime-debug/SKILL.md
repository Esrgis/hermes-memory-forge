---
name: guild-runtime-debug
description: Use when a Hermes Guild run looks fake, too fast, stuck, double-submitted, misrouted, failed after preview/run, or when checking whether workers, adapters, finalizer, and files actually did what the dashboard implies.
---

# Guild Runtime Debug

Use runtime evidence, not board appearance.

## Evidence Ladder

1. Read `_runtime/dashboard/guild-events.jsonl` tail for route events.
2. Inspect `_runtime/guild-worker-agent/*payload.json` for adapter attempts and blocked reasons.
3. Inspect `guild-workspaces/<quest-id>/` for actual files.
4. Check dashboard JSON only as display state, not truth.
5. Inspect process state only when needed, and verify exact process identity before stopping anything.

## What To Report

- Whether the run was preview-only, local smoke, or real provider path.
- The quest id.
- The route events: plan preview, quest creation, wake, worker profile, finalizer.
- The adapter path and blocked reason for failures.
- Whether expected files exist.
- Whether workers were actually launched.

## Common Failure Patterns

- Preview succeeds, Confirm Run fails: usually planner schema mismatch or create-task validation.
- Run looks instant: often deterministic `local-file-writer` or `local-dry-run`.
- Board shows done but files missing: artifact JSON passed without filesystem grounding.
- Finalizer spam: auto-refresh/finalizer loop is retrying while review is blocked/failed.
- Duplicate events: UI double-submit or browser retry.

## Guardrails

- Do not call dashboard launchers while debugging logs unless the user explicitly asks.
- Do not stop processes without showing the exact matching process first.
- Keep provider key reporting boolean-only.
- Do not dump raw logs into Obsidian.
