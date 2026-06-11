# Guild claim/resume lesson — 2026-06-05

## Trigger

Dashboard/state symptom: a Guild quest can appear stuck with a task in `claimed`/`running` while downstream review remains `blocked` with `waiting_deps`.

Observed target quest: `quest-manual-dashboard-task-20260605141838`.

## Evidence checked

Bounded evidence sources only: dashboard event log, durable Guild task DB, worker terminal session logs, existing payload files, and quest workspace.

For `quest-manual-dashboard-task-20260605141838`:

- Planner preview selected template `standard-build`.
- Workspace files present: `task-brief.md`, `hermes-plan.json`, `implementation.md`.
- Missing expected verification/review outputs: `verification.md`, `review.md`, final artifacts.
- Durable DB currently records:
  - spec: `done`
  - task-2: `done` by `worker-a`
  - task-3: currently `failed` by `worker-c`
  - review: `blocked`, waiting on task-3 dependency
- Worker-c terminal evidence shows it did eventually process task-3 and marked it failed with `invalid_adapter_output`.
- Payload evidence currently exists for worker-c, so the live quest is no longer a pure stuck-claimed example at inspection time.

## Root cause class

The code-level failure mode is real even if the inspected live quest later advanced to `failed`:

- `_runtime/flock/worker_team_prototype.py::claim_next_task` only selected `status = 'open'` tasks.
- It updated claims only with `where status = 'open'`.
- A worker that already owned a valid lease on a `claimed`/`running` task had no resume path through `claim-next`.
- If a worker claimed a task and then failed before adapter execution/progress logging, later loop iterations could report idle instead of resuming its own task.

## Durable rule

Worker loops must support both paths:

1. Resume own active leases:
   - `status in ('claimed', 'running')`
   - `assignee_id == current agent`
   - `lease_until` is still valid
   - rank/skill still match

2. Release expired claims before normal reuse:
   - expired claimed/running tasks can be released and later claimed normally
   - workers must not steal another agent's still-active lease

## Fix applied

Added a safe resume path before normal open-task claiming in `_runtime/flock/worker_team_prototype.py::claim_next_task`.

Behavior:

- Same-agent valid claimed/running lease returns as `claimed: true`, `resumed: true` and extends heartbeat/lease.
- Other-agent active claimed/running tasks are not claimable.
- Expired claimed/running tasks remain handled by the existing `release-expired` command before normal claiming.

## Focused no-provider tests

Added `scripts/test-guild-claim-resume-smoke.py` covering:

- claimed task assigned to same agent can be resumed/returned to that agent
- claimed task assigned to another agent is not claimed
- expired claimed task can be released and later claimed normally
- review stays blocked until dependency task is done

## Verification commands

No UI launch, no dashboard server launch, no provider calls.

```bash
python -m py_compile _runtime/flock/worker_team_prototype.py scripts/test-guild-claim-resume-smoke.py
python scripts/test-guild-claim-resume-smoke.py
python scripts/test-guild-artifact-validation-smoke.py
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/test-guild-worker-artifact-validation-smoke.ps1
```

## Limitation

This verifies the no-provider scheduler/validator behavior only. Do not claim dashboard/UI/provider E2E fixed until a fresh real quest creates all expected files on disk and dashboard state matches filesystem state.
