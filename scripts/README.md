# Scripts

Scripts are split into stable setup helpers and local/incubator automation.

## Stable Setup Helpers

These are intended to be reusable with parameters:

- `setup-workspace.ps1`
- `scaffold-obsidian.ps1`
- `new-daily-note.ps1`
- `set-hermes-profile.ps1`
- `send-telegram-home.ps1`
- `search-files.ps1`
- `search-content.ps1`
- `preview-file.ps1`
- `inspect-workspace.ps1`
- `find-process.ps1`
- `open-notepad-plus-plus.ps1`

## Incubator / Local Automation

These are useful on the current workstation, but should be treated as examples until their contracts are hardened:

- `blackboard.py`
- `guild-worker-team.py`
- `get-guild-agent-profile.ps1`
- `get-guild-provider-adapter.ps1`
- `configure-guild-worker.ps1`
- `invoke-guild-provider-adapter.ps1`
- `invoke-hermes.ps1`
- `invoke-hermes-guild.ps1`
- `invoke-hermes-opencode-task.ps1`
- `run-guild-worker-agent.ps1`
- `start-guild-worker-terminal.ps1`
- `obsidian-memory-index.py`
- `build-obsidian-memory-index.ps1`
- `search-obsidian-memory.ps1`
- `build-daily-brief.py`
- `content_factory.py`
- `send-daily-brief-home.ps1`
- `send-game-checkin.ps1`
- `mark-game-checkin.ps1`
- `hermes-healthcheck.ps1`

Do not move these scripts while Hermes cron jobs or local shortcuts may still reference their current paths.

## Hermes Entrypoints

- `invoke-hermes.ps1`: Secretary-mode Hermes wrapper. It injects shared Current State and runtime routing context.
- `invoke-hermes-guild.ps1`: Guild-manager Hermes wrapper. It injects manager bootstrap, shared Current State, Guild config, and provider contracts.
- Both wrappers auto-run `close-session-memory.ps1 -Apply` after successful real calls. Use `-DryRun` to inspect injection/hook state without model calls, or `-NoSessionMemory` for intentionally stateless calls.

## Session Checkpoint Memory

Use checkpoint events to preserve flow ownership without writing raw chat logs. Events stay in `_runtime/session-checkpoints/` until flushed.

Flow:

```text
milestone -> add-session-checkpoint.ps1 -> _runtime/session-checkpoints/*.json
substantial slice -> flush-session-checkpoints.ps1 -DryRun
clean candidate -> flush-session-checkpoints.ps1 -Apply
-> Daily/YYYY-MM-DD.md + System/Assistant/Shared/Current State.md
```

Examples:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\add-session-checkpoint.ps1 -Kind decision -Summary "Use Guild Runtime contract-first; keep Flock as reference." -MemoryValue high
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\add-session-checkpoint.ps1 -Kind test -Summary "Notepad++ dry-run returned created_file=false and would_create_file=true." -Evidence "open-notepad-plus-plus.ps1 -DryRun -Json" -MemoryValue medium
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\flush-session-checkpoints.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\flush-session-checkpoints.ps1 -Apply
```

Rules:

- Store timestamped distilled events, not raw chat logs.
- Low/noise events remain skipped unless `-IncludeLow` is used.
- Flush uses `close-session-memory.ps1`, so Obsidian writes stay allowlisted.

See `docs/core/SESSION_CHECKPOINT_MEMORY.md` for the full flow and promotion rules.

## Content Factory MVP

`content_factory.py` is a local-first MVP queue for TikTok/Shorts candidates with human approval. It intentionally uses SQLite and runtime artifacts under `_runtime/content-factory/` instead of the full Guild worker runtime.

Useful commands:

```powershell
python .\scripts\content_factory.py init --json
python .\scripts\content_factory.py create-job --topic "AI workflow" --niche "local-first automation" --language vi --json
python .\scripts\content_factory.py generate-script --job-id JOB_ID --json
python .\scripts\content_factory.py render-placeholder --job-id JOB_ID --json
python .\scripts\content_factory.py send-approval --job-id JOB_ID --dry-run --json
python .\scripts\content_factory.py mark-decision --job-id JOB_ID --decision approved --json
```

See `docs/content-factory/MVP.md` and `docs/content-factory/n8n/` for the n8n workflow skeleton.

## Guild UI Demo (Canonical Entrypoints)

If you only remember the core files for the UI-first Guild demo, remember these:

- Dashboard UI: `docs/incubation/guild-dashboard.html`
- Dashboard API server: `scripts/guild-dashboard-server.py`
- Open dashboard (canonical launcher): `scripts/open-guild-dashboard.ps1`
- Quick dashboard command (wrapper): `scripts/guild.ps1` (installed as `guild` by `scripts/install-guild-command.ps1`)
- Launch visible worker terminal loop: `scripts/start-guild-worker-terminal.ps1`
- Worker tick core: `scripts/run-guild-worker-agent.ps1`
- Provider adapter runtime (canonical Python): `scripts/guild_provider_adapters/invoke.py`
- Guild runtime config: `config/guild/`

Flow (one button):

`guild-dashboard.html` -> `POST /api/quest/manual` -> `POST /api/wake` -> worker terminals -> `GET /api/dashboard` (auto-refresh).

State:

- SQLite: `%LOCALAPPDATA%\\hermes\\flock\\worker_team.sqlite`
- Export JSON: `_runtime/dashboard/guild-dashboard.json`

Notes:

- UI “Hermes Routing Log” is routing/progress for the demo (not Hermes gateway events, not chain-of-thought).
- `invoke-guild-provider-adapter.ps1` is a compatibility wrapper; adapter logic lives under `scripts/guild_provider_adapters/`.

## Guild Worker Team Prototype

`guild-worker-team.py` is the tracked incubator launcher for the Guild Worker Team contract. It delegates to the current runtime prototype under `_runtime/flock/`, which reads and writes durable task/artifact state under the Hermes AppData SQLite path by default. Optional Flock source dependencies remain under `_runtime/research/flock/`.

Useful smoke commands:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id smoke-join-chain --include-tasks --include-artifacts --format text
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id smoke-join-chain
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py list-tasks --limit 5
_runtime\research\flock\.venv\Scripts\python.exe _runtime\flock\worker_team_prototype.py run-fake-worker --quest-chain-id smoke-fake-loop --agent-id fake-smoke-worker --agent-rank S --skills general --max-steps 5
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\open-guild-dashboard.ps1 -QuestChainId demo-even-random-app
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\open-guild-dashboard.ps1 -QuestChainId demo-even-random-app -Reset
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tick-guild-dashboard.ps1 -QuestChainId demo-even-random-app -MaxSteps 1
```

JSON remains the default dashboard output for future UI/API consumers. Use `--format text` for human terminal review.

## Guild Worker Profiles

Worker profile docs live in `docs/workers/`.

- `docs/workers/WORKER_BOOTSTRAP.md`: short route map for weak/model-backed workers.
- `docs/workers/HERMES_MANAGER_BOOTSTRAP.md`: compact boot contract for Hermes as Guild manager.
- `docs/workers/AGENT_PROFILES.md`: human-readable profile summary.
- `docs/workers/PROVIDER_ADAPTERS.md`: provider adapter contract, without secrets.
- `config/guild/agent-profiles.json`: machine-readable profile source.
- `config/guild/capability-adapters.json`: gun policy for visible scope, permissions, artifact schema, and ammo ladders.
- `config/guild/model-cartridges.json`: concrete model ammo inventory.
- `config/guild/provider-transports.json`: gateway/API/CLI transport inventory.
- `config/guild/provider-adapters.json`: legacy backend adapter compatibility map.
- `scripts/guild_provider_adapters/`: Python adapter runtime used by `invoke-guild-provider-adapter.ps1`.
- `_runtime/guild-worker-agent/provider-selection.json`: local active provider selection written by `configure-guild-worker.ps1`.

Useful profile commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\get-guild-agent-profile.ps1 -Profile builder
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\get-guild-provider-adapter.ps1 -Adapter local-dry-run
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -List
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile builder -Adapter auto-ammo -Capability code-edit-worker -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile builder -Adapter opencode -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile builder -Adapter openrouter -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile tester -Adapter gemini -Model gemini-2.5-flash -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile builder -Adapter groq -Model openai/gpt-oss-20b -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter local-dry-run -Profile builder -Message "Return a smoke result."
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter auto-ammo -Capability deterministic-smoke -Profile builder -Message "Return a smoke result."
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter opencode -Profile builder -Message "Return exactly this JSON and do not modify files: {\"ok\":true}"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter groq -Profile builder -Model openai/gpt-oss-20b -Message "Return exactly this JSON: {\"ok\":true,\"summary\":\"groq smoke\",\"files_changed\":[],\"commands_run\":[\"groq smoke\"],\"test_result\":\"not_required\",\"known_risks\":[],\"blocked_reason\":null}"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-hermes-guild.ps1 "Nói ngắn gọn Guild hiện có những provider nào?"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-guild-worker-agent.ps1 -Profile builder -Adapter local-dry-run -QuestChainId demo-even-random-app -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-guild-worker-agent.ps1 -UseConfiguredProvider -QuestChainId demo-even-random-app -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-guild-worker-agent.ps1 -Profile builder -Adapter invalid-output-smoke -QuestChainId smoke-invalid-output-v1 -TaskId smoke-invalid-output-agent-v1 -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-hermes-opencode-task.ps1 -TaskId smoke-opencode-agent -QuestChainId demo-opencode-handoff -CreateIfMissing -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-hermes-opencode-task.ps1 -TaskId smoke-opencode-visible -QuestChainId demo-opencode-handoff -CreateIfMissing -VisibleWorker -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-guild-worker-terminal.ps1 -Profile builder
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-guild-worker-terminal.ps1 -Profile tester
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-guild-worker-terminal.ps1 -Profile reviewer
```

The terminal launcher currently runs the deterministic worker loop. It is intentionally visible so early dashboard states correspond to an actual local process.

## Obsidian FTS Search

`obsidian-memory-index.py` is the first local retrieval layer for durable Obsidian memory. It indexes markdown into SQLite FTS5 outside the vault.

```powershell
python .\scripts\obsidian-memory-index.py build --vault-path D:\Path\To\MemoryCore
python .\scripts\obsidian-memory-index.py search "daily brief"
python .\scripts\obsidian-memory-index.py stats

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-obsidian-memory-index.ps1 -VaultPath D:\Path\To\MemoryCore
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\search-obsidian-memory.ps1 -Query "daily brief"
```

This is RAG plumbing, not full vector RAG. It returns file paths, headings, and snippets so Hermes or another agent can decide what to read next.

## Searchable Workspace

This workspace treats the filesystem as a searchable space, not a folder tree to crawl manually.

Use standard routes before falling back to raw PowerShell:

```text
find paths    -> search-files.ps1       -> Everything ES, fd, scoped PowerShell
search text   -> search-content.ps1     -> rg, scoped PowerShell
preview file  -> preview-file.ps1       -> bat, Get-Content
inspect root  -> inspect-workspace.ps1  -> eza, Get-ChildItem
navigation    -> zoxide is for the human shell, not agent automation
```

## Process Inspection / Safe Stop

`find-process.ps1` is the standard bounded route for Windows process lookup. It wraps `Get-CimInstance Win32_Process` so Hermes/agents do not need ad hoc process pipelines.

Default behavior is read-only. Stop actions are guarded:

- no broad process listing without `-ProcessId`, `-Name`, or `-Pattern`
- `-Stop` refuses multiple matches unless `-AllowMultiple` is passed
- Hermes/gateway/agent runtime processes are protected unless `-AllowHermes` is explicitly passed
- use `-DryRun` before stopping anything ambiguous

Examples:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\find-process.ps1 -Pattern "hermes_cli.main gateway run" -LeafOnly -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\find-process.ps1 -Name "notepad" -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\find-process.ps1 -ProcessId 1234 -Stop -DryRun -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\find-process.ps1 -ProcessId 1234 -Stop -Json
```

## Open Notepad++

`open-notepad-plus-plus.ps1` is the standard route for asking Hermes to open Notepad++ with prepared text. It writes a UTF-8 scratch file under `_runtime/notepad-plus-plus/` and opens that file in Notepad++, avoiding brittle keyboard automation such as `Ctrl+N` and `SendKeys`.

Examples:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\open-notepad-plus-plus.ps1 -Text "Nội dung cần ghi" -Title "ghi-chu" -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\open-notepad-plus-plus.ps1 -Text "Nội dung cần ghi" -Title "ghi-chu" -DryRun -Json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\open-notepad-plus-plus.ps1 -InputFile .\Prompt.md -Json
```

Enable/check the runtime manifest for Hermes or other agents:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\enable-searchable-workspace.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\enable-searchable-workspace.ps1 -CheckOnly
```

The default command writes `_runtime/searchable-workspace/manifest.json` and sets the user environment variable `HERMES_SEARCHABLE_WORKSPACE` to that manifest path. It does not install tools unless `-InstallMissing` is explicitly passed.

### File Discovery

`search-files.ps1` is the standard bounded file-discovery route on Windows.

Flow:

```text
Everything ES
-> fd scoped to -Root
-> scoped PowerShell fallback
```

Example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\search-files.ps1 -Query "AGENTS.md" -Root D:\HermesGuildCore -Limit 20
```

Everything ES is option 1 when the Everything IPC service is running. If ES fails, the script immediately falls back to scoped local search.

Inside the Codex sandbox, Everything IPC may be blocked even when the Everything service is healthy for the normal user session. Treat that as an expected fast-path failure and let the script fall back.

### Content Search

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\search-content.ps1 -Pattern "Guild Runtime" -Path . -Limit 40
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\search-content.ps1 -Pattern "dashboard" -Path .\_obsidian_vault -Glob "*.md" -Limit 40
```

### File Preview

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\preview-file.ps1 -Path .\START_HERE.md -Lines 80
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\preview-file.ps1 -Path .\TASKS.md -Start 20 -Lines 60
```

### Workspace Inspection

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\inspect-workspace.ps1 -Path . -Limit 60
```

Do not replace these with ad hoc recursive `Get-ChildItem` or `Select-String` unless the standard route fails or a very small known directory is being inspected.

## Shared Cognition Update

Use this after meaningful sessions to update shared Codex/Hermes reflex memory without dumping raw logs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\update-shared-cognition.ps1 -Summary "Hermes capability adapters are guns; providers/models are ammo." -Reflex "Keep permissions fixed when swapping ammo." -Rule "Do not store raw chat logs." -NextAction "Wire post-session update into the close workflow."
```

Target note: `_obsidian_vault/System/Assistant/Shared/Cognition Reflexes.md`.
