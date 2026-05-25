# Handoff: UI Guild Demo 2026-05-22

Use this file to continue in a fresh Codex window when context is low.

## User Goal

The user wants a UI-first demo, not a CLI-first demo:

```text
User enters one task
-> clicks one button: "Giao Task Cho Hermes"
-> Hermes progress log appears above the board
-> tasks are split by fixed prompt/rules, not heavy autonomous planning
-> tasks go to blackboard
-> workers/adapters are woken automatically
-> visible terminals show progress/evidence logs
-> dashboard board updates through Ready / Claimed / Blocked / Done
```

The UI should not have a separate `Wake Workers` button. Wake should happen automatically after assignment.

The Hermes log must be a progress/routing log, not hidden chain-of-thought.

## Current Percent

For the UI demo target above: about 90%.

Done:

- Blackboard task/artifact runtime.
- Four-column dashboard.
- One-button UI flow.
- Local dashboard API server.
- Manual fixed DAG split: `spec -> build-1/build-2/build-3 -> review`.
- Auto wake API route.
- Worker terminal launcher path.
- Worker-agent loop.
- Adapter runtime.
- Output validation.
- Least-context worker prompt envelope.
- Durable `needs_info` blocked artifact path.
- Crash-course learning doc.

Now verified:

- One real wake with visible `local-dry-run` terminals.
- Dashboard API auto-refresh source moved build/test/review through `done`.
- Parallel-first router smoke on port `8783`: `quest-parallel-router-smoke-20260522-1515` created `spec -> build-1/build-2/build-3 -> review`, all three build tasks were claimed before review, reviewer had `no_claimable_task` while builds were claimed, and review unlocked only after all builds were `done`.
- Needs-info smoke: `quest-needs-info-smoke-20260522-1535` published artifact `artifact-e88c7606`, set build task `blocked`, preserved `block_reason=needs_info`, and `unlock-ready` did not reopen it.
- Final local UI demo smoke on port `8785`: `quest-final-ui-demo-local-20260522` launched three builder terminals plus one reviewer terminal, reached `done=5`, and published four artifacts.
- The dashboard UI was opened at `http://127.0.0.1:8785/docs/incubation/guild-dashboard.html`.

Still needed:

- Polish terminal progress logs if they are too noisy.
- Only after that, try `opencode`; it has token/sandbox/provider quirks.

## Routing Contract

This week is `manual-router v0`.

The dashboard server uses a fixed prompt/rules split, not autonomous planning:

```text
spec done
-> build-1/build-2/build-3 open in parallel
-> review blocked until all build tasks are done
```

Next week, Hermes planner can replace this fixed split with autonomous DAG planning after the local-dry-run UI path is smooth.

## Important Files

Dashboard UI:

```text
docs/incubation/guild-dashboard.html
```

Dashboard local API server:

```text
scripts/guild-dashboard-server.py
```

Dashboard launcher:

```text
scripts/open-guild-dashboard.ps1
```

Visible worker terminal launcher:

```text
scripts/start-guild-worker-terminal.ps1
```

Worker execution loop:

```text
scripts/run-guild-worker-agent.ps1
```

Adapter runtime:

```text
scripts/guild_provider_adapters/
```

Learning doc:

```text
docs/learning/HERMES_GUILD_RUNTIME_CRASH_COURSE.md
```

Runtime state:

```text
C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite
_runtime/dashboard/guild-dashboard.json
```

## Current Dashboard Server

Latest verified UI demo server was started on:

```text
http://127.0.0.1:8785/docs/incubation/guild-dashboard.html
```

Fresh server health returned `version=0.2`, workspace `D:\HermesGuildCore`, and DB path `C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite`.

Final local demo quest:

```text
quest-final-ui-demo-local-20260522
```

Final local demo evidence:

```text
spec done
build-1 done -> artifact implementation_result_1
build-2 done -> artifact implementation_result_2
build-3 done -> artifact implementation_result_3
review done  -> artifact integration_report
```

## Shutdown Handoff

The user is shutting down after the local demo.

Do not rely on provider state from the current process after reboot. Keys were not exposed in chat and should not be committed.

Provider status before shutdown:

```text
local-dry-run demo: passed
opencode tiny adapter smoke: can return valid JSON
opencode worker-sized prompt: not stable yet; saw invalid output / Windows wrapper prompt issues / timeout
openrouter direct adapter: added, but current process lacked OPENROUTER_API_KEY
opencode.json: uses {env:NINE_ROUTER_API_KEY}, not literal key
```

Recommended next provider retry:

```powershell
$env:OPENROUTER_API_KEY = '<local key, do not print>'
.\scripts\invoke-guild-provider-adapter.ps1 -Adapter openrouter -Profile builder -Title provider-smoke-openrouter -Message 'Return only compact JSON: {"ok":true,"summary":"openrouter smoke","files_changed":[],"commands_run":["openrouter smoke"],"test_result":"not_required","known_risks":[],"blocked_reason":null}' -Json
```

If that passes, run one worker task with `-Adapter openrouter` before trying full UI wake.

Real wake smoke passed for:

```text
quest-real-one-button-ui-wake-8781
```

Poll evidence:

```text
build  -> done by builder
test   -> done by tester
review -> claimed by reviewer, then done on next poll
```

Clean test server was started on:

```text
http://127.0.0.1:8780/docs/incubation/guild-dashboard.html
```

Smoke passed:

```text
GET /api/health
POST /api/quest/manual
```

`/api/quest/manual` created:

```text
quest-one-button-smoke
```

Port `8765` may have an old/stale server from earlier experiments. The server health route now includes:

```json
{
  "ok": true,
  "service": "guild-dashboard",
  "version": "0.2",
  "workspace": "...",
  "db_path": "..."
}
```

`open-guild-dashboard.ps1` rejects a stale server if the DB path does not match.

## One-Button UI Behavior

The UI form submit handler now does:

```text
POST /api/quest/manual
-> POST /api/wake
-> render dashboard
-> enable auto-refresh
```

The single visible user action is:

```text
Giao Task Cho Hermes
```

The old separate `Wake Workers` button was removed.

## Manual Quest API

Endpoint:

```http
POST /api/quest/manual
```

Body shape:

```json
{
  "title": "One button smoke",
  "request": "Check one button Hermes task flow.",
  "adapter": "local-dry-run",
  "allowed_files": "docs/incubation/*"
}
```

Server creates:

```text
<slug>-spec     status done
<slug>-build-1  status open, depends on spec
<slug>-build-2  status open, depends on spec
<slug>-build-3  status open, depends on spec
<slug>-review   status blocked, depends on build-1 + build-2 + build-3
```

## Wake API

Endpoint:

```http
POST /api/wake
```

Body shape:

```json
{
  "quest_chain_id": "quest-one-button-smoke",
  "adapter": "local-dry-run",
  "profiles": ["builder", "builder", "builder", "reviewer"]
}
```

Dry-run smoke already passed with:

```json
{
  "dry_run": true,
  "profiles": ["builder"]
}
```

Real wake has already passed for the old sequential chain. For the parallel-first chain, use three builder launches plus reviewer.

## Commands To Continue

Start dashboard on a fresh port:

```powershell
.\scripts\open-guild-dashboard.ps1 -QuestChainId quest-one-button-smoke -Port 8781
```

Health:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8781/api/health'
```

Create task via API:

```powershell
$body = @{
  title = 'Real wake smoke'
  request = 'Check one button Hermes task flow.'
  adapter = 'local-dry-run'
  allowed_files = 'docs/incubation/*'
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8781/api/quest/manual' -Method Post -ContentType 'application/json' -Body $body
```

Wake real terminals:

```powershell
$body = @{
  quest_chain_id = 'quest-real-wake-smoke'
  adapter = 'local-dry-run'
  profiles = @('builder','builder','builder','reviewer')
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8781/api/wake' -Method Post -ContentType 'application/json' -Body $body
```

If testing without opening windows:

```powershell
$body = @{
  quest_chain_id = 'quest-real-wake-smoke'
  adapter = 'local-dry-run'
  profiles = @('builder')
  dry_run = $true
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8781/api/wake' -Method Post -ContentType 'application/json' -Body $body
```

## Tooling Note

Workspace rules prefer wrappers:

```text
scripts/search-files.ps1    -> Everything ES first, fallback to fd/PowerShell
scripts/search-content.ps1  -> rg first
scripts/preview-file.ps1    -> bat/Get-Content
scripts/inspect-workspace.ps1 -> eza/Get-ChildItem
```

So if it looks like Codex did not use raw `rg`, `es`, or `eza`, it often used the repo-approved wrapper that calls them.

Do not depend on Flow Launcher / `fl` for automation. It is human navigation/UI state, not agent backend state.

## Known Issues

- Old server processes can remain on earlier ports. Prefer a fresh port or check `/api/health` version/db_path.
- OpenCode can fail inside sandbox with `uv_spawn 'git'`.
- OpenCode tiny prompts still cost about 13k input tokens.
- `opencode -Provider 9router -Model openrouter/qwen/qwen3-coder:free` reaches the route but provider auth fails with 401 until credentials are fixed.
- Direct `openrouter` and `gemini` adapters are selectable but not implemented.
- `needs_info` must remain `blocked`, not auto-unlocked. This is now covered by `blocked_reason=needs_info` persisted in the task payload.

## Learning Docs

The main learning file is:

```text
docs/learning/HERMES_GUILD_RUNTIME_CRASH_COURSE.md
```

It explains:

- why JSON artifacts matter
- why adapters exist
- blackboard semantics
- UI/API/worker/adapter code walkthrough
- smoke-test workflow
- senior debugging loop
- common libraries/tools used
- 7-day study plan

## Next Best Step

If the user wants a provider-backed demo after reboot, run exactly one OpenRouter direct smoke first and treat provider/auth/token issues as structured blocked artifacts.

Do not implement direct `openrouter`/`gemini` before deciding whether OpenRouter should route through OpenCode/9Router or a direct adapter.
