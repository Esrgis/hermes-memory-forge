# Guild Artifact Schema Lesson — 2026-06-05

## 1. Trigger

Artifact validation failed with `invalid_adapter_output` even though the provider returned useful `ok=true` artifact JSON.

## 2. Evidence

- Quest: `quest-manual-dashboard-task-20260605100507`
- Failed worker: `worker-c`
- `blocked_reason`: `invalid_adapter_output`
- Missing file: `build-3.md`
- Reviewer/finalizer did not complete because upstream task-3 failed.

No raw payload JSON is stored in this note.

## 3. Root cause

- The successful artifact omitted `blocked_reason`.
- Both validators required `blocked_reason`.
- Schema behavior was duplicated across:
  - `scripts/guild_provider_adapters/validation.py`
  - `scripts/run-guild-worker-agent.ps1`

## 4. Durable rule

- For `ok=true` artifacts, missing `blocked_reason` should normalize to `null`.
- For `ok=false` artifacts, `blocked_reason` must remain required.
- Any future artifact schema normalization must be mirrored in both Python adapter validation and PowerShell worker validation, or the runtime can pass one layer and fail another.

## 5. Verification commands

```bash
python scripts/test-guild-artifact-validation-smoke.py
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/test-guild-worker-artifact-validation-smoke.ps1
```

## 6. Limitation

This proves the no-provider validator/schema bug is fixed. It does not prove full real-provider E2E until a new provider run creates `build-3.md`, `review.md`, `final-summary.md`, and `final-artifact.json`.
