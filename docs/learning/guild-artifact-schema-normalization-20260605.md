# Guild artifact schema normalization learning — 2026-06-05

Quest: `quest-manual-dashboard-task-20260605100507`

## Trigger

Artifact validation failed because the accepted artifact schema drifted between:

- Python adapter validation: `scripts/guild_provider_adapters/validation.py`
- PowerShell worker validation: `scripts/run-guild-worker-agent.ps1`

## Evidence

`worker-c` failed with `blocked_reason=invalid_adapter_output` even though the provider returned useful `ok=true` artifact JSON text. The immediate schema issue was a missing `blocked_reason` field.

No raw payload logs are stored here; this is only the distilled finding.

## Lesson

Schema normalization rules must be mirrored in both validation layers:

1. Python adapter validation.
2. PowerShell worker validation.

If one layer accepts or normalizes a shape, the other must behave the same way.

## Fix

Fixed files:

- `scripts/guild_provider_adapters/validation.py`
- `scripts/run-guild-worker-agent.ps1`

Runtime rule after the fix:

- Successful artifact may omit `blocked_reason`; runtime normalizes it to `null`.
- Failed artifact must still report `blocked_reason`.

## Verification

No-provider smokes:

```bash
python scripts/test-guild-artifact-validation-smoke.py
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/test-guild-worker-artifact-validation-smoke.ps1
```

## Limitation

Full real-provider E2E was not rerun, so this only verifies the schema/validation fix and captured-artifact revalidation path.
