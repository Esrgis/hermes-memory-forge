# Path And Cache Audit - 2026-05-31

Purpose: reduce path confusion and prepare for safe cache cleanup without touching durable memory or external junctions.

## Inspected Paths

```text
D:\HermesGuildCore                  real directory
D:\HermesGuildCore\_runtime         real directory, ignored runtime/cache/artifacts
D:\HermesGuildCore\guild-workspaces real directory, ignored quest artifacts
D:\HermesGuildCore\_obsidian_vault  junction -> D:\HermesVault\MemoryCore
```

Rule: `_obsidian_vault` is not cache. Do not delete, rename, or clean it as part of disk cleanup.

## Current Runtime Buckets

- Durable local SQLite: `%LOCALAPPDATA%\hermes\flock\worker_team.sqlite`, `%LOCALAPPDATA%\hermes\blackboard\*.sqlite`, `%LOCALAPPDATA%\hermes\content-factory\content_factory.sqlite`.
- Workspace runtime/cache: `_runtime/dashboard/`, `_runtime/guild-worker-agent/`, `_runtime/guild-provider-adapters/`, `_runtime/content-factory/`, `_runtime/n8n-*`, `_runtime/research/`.
- Quest artifacts: `guild-workspaces/<quest_chain_id>/`.
- Demo-only temporary DBs: `%TEMP%\hermes-guild-e2e-demo.sqlite`, `%TEMP%\hermes-guild-doubleclick-demo.sqlite`.
- Local secrets: `_runtime/provider-secrets.local.ps1`; ignored, not cache, do not print or delete casually.

## Cleanup Direction

Next safe step is a dry-run-only script that reports size and age for known ignored folders:

- `_runtime/dashboard/`
- `_runtime/guild-worker-agent/`
- `_runtime/guild-provider-adapters/`
- old `guild-workspaces/quest-*`
- `%TEMP%\hermes-guild-*.sqlite`

Do not include:

- `_obsidian_vault`
- `_hermes`
- `_runtime/provider-secrets.local.ps1`
- `%LOCALAPPDATA%\hermes\*.sqlite` unless explicitly backed up and approved
- `.git`

## Standardization Candidate

Added `config/runtime-paths.json` to name path roles:

```json
{
  "durable_state": "%LOCALAPPDATA%/hermes",
  "workspace_runtime": "_runtime",
  "quest_artifacts": "guild-workspaces",
  "temp_demos": "%TEMP%/hermes-guild-*.sqlite"
}
```

Added `scripts/audit-runtime-paths.ps1` as a read-only audit route. Default mode checks existence, link type, target, attributes, and cleanup policy without measuring folder size:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\audit-runtime-paths.ps1
```

Use `-MeasureSize` only for known scoped runtime folders when disk usage matters; it recursively measures only configured targets.

## Dry-Run Cleanup Route

Added `scripts/cleanup-runtime-paths.ps1` as a dry-run-only cleanup candidate reporter. It has no delete/apply mode.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cleanup-runtime-paths.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cleanup-runtime-paths.ps1 -OlderThanDays 3 -MeasureSize
```

It only reports known ignored runtime/demo buckets:

- selected `_runtime` children
- old `guild-workspaces/quest-*`
- `%TEMP%/hermes-guild-*.sqlite`

It explicitly skips vault links, Hermes links, local provider secrets, durable AppData SQLite, and `.git`.

## Dry-Run Smoke Results

Passed on 2026-05-31:

```powershell
& .\scripts\audit-runtime-paths.ps1
& .\scripts\cleanup-runtime-paths.ps1 -OlderThanDays 0 -MeasureSize
& .\scripts\start-guild-worker-terminal.ps1 -Profile worker-a -QuestChainId dry-run-smoke -Adapter local-dry-run -DryRun
& .\scripts\invoke-guild-provider-adapter.ps1 -Adapter local-dry-run -Profile worker-a -Title dry-run-smoke -Message 'Return a dry-run artifact.' -Json
& .\scripts\send-telegram-home.ps1 -Text 'Hermes dry-run smoke only' -DryRun
& .\scripts\hermes-healthcheck.ps1 -DryRun
& .\scripts\send-daily-brief-home.ps1 -DryRun
& .\scripts\update-shared-cognition.ps1 -Summary 'Dry-run smoke for shared cognition update.' -DryRun
python .\scripts\content_factory.py send-approval --job-id job-telegram-20260527 --dry-run --json
```

Dashboard API dry-run also passed using a temp DB and stopped server process:

```text
POST /api/wake dry_run=true -> worker-a launched=false, dry_run=true
run-guild-worker-agent.ps1 with empty temp DB -> ok=true, reason=no_claimable_task
```

Fixes from the dry-run pass:

- `scripts/hermes-healthcheck.ps1 -DryRun` now reports what it would check without requiring `hermes` CLI or writing blackboard events.
- `scripts/content_factory.py` falls back to fixed UTC+7 when Python `tzdata` is missing.
- `scripts/build-daily-brief.py` uses the same UTC+7 fallback.
- `scripts/content_factory.py send-approval --dry-run` now returns before status/event writes.
