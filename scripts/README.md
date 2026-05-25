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

## Incubator / Local Automation

These are useful on the current workstation, but should be treated as examples until their contracts are hardened:

- `blackboard.py`
- `guild-worker-team.py`
- `get-guild-agent-profile.ps1`
- `get-guild-provider-adapter.ps1`
- `configure-guild-worker.ps1`
- `invoke-guild-provider-adapter.ps1`
- `invoke-hermes-opencode-task.ps1`
- `run-guild-worker-agent.ps1`
- `start-guild-worker-terminal.ps1`
- `obsidian-memory-index.py`
- `build-obsidian-memory-index.ps1`
- `search-obsidian-memory.ps1`
- `build-daily-brief.py`
- `send-daily-brief-home.ps1`
- `send-game-checkin.ps1`
- `mark-game-checkin.ps1`
- `hermes-healthcheck.ps1`

Do not move these scripts while Hermes cron jobs or local shortcuts may still reference their current paths.

## Guild UI Demo (Canonical Entrypoints)

If you only remember the core files for the UI-first Guild demo, remember these:

- Dashboard UI: `docs/incubation/guild-dashboard.html`
- Dashboard API server: `scripts/guild-dashboard-server.py`
- Open dashboard (canonical launcher): `scripts/open-guild-dashboard.ps1`
- Quick dashboard command (wrapper): `scripts/guild.ps1` (installed as `guild` by `scripts/install-guild-command.ps1`)
- Launch visible worker terminal loop: `scripts/start-guild-worker-terminal.ps1`
- Worker tick core: `scripts/run-guild-worker-agent.ps1`
- Provider adapter runtime (canonical Python): `scripts/guild_provider_adapters/invoke.py`

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
- `docs/workers/AGENT_PROFILES.md`: human-readable profile summary.
- `docs/workers/agent-profiles.json`: machine-readable profile source.
- `docs/workers/PROVIDER_ADAPTERS.md`: provider adapter contract, without secrets.
- `docs/workers/provider-adapters.json`: machine-readable provider adapter source.
- `scripts/guild_provider_adapters/`: Python adapter runtime used by `invoke-guild-provider-adapter.ps1`.
- `_runtime/guild-worker-agent/provider-selection.json`: local active provider selection written by `configure-guild-worker.ps1`.

Useful profile commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\get-guild-agent-profile.ps1 -Profile builder
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\get-guild-provider-adapter.ps1 -Adapter local-dry-run
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -List
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile builder -Adapter opencode -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile tester -Adapter gemini -Model gemini-2.5-flash -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure-guild-worker.ps1 -Profile builder -Adapter groq -Model openai/gpt-oss-20b -TestNow
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter local-dry-run -Profile builder -Message "Return a smoke result."
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter opencode -Profile builder -Message "Return exactly this JSON and do not modify files: {\"ok\":true}"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\invoke-guild-provider-adapter.ps1 -Adapter groq -Profile builder -Model openai/gpt-oss-20b -Message "Return exactly this JSON: {\"ok\":true,\"summary\":\"groq smoke\",\"files_changed\":[],\"commands_run\":[\"groq smoke\"],\"test_result\":\"not_required\",\"known_risks\":[],\"blocked_reason\":null}"
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
