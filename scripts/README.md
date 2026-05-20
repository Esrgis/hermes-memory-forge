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

## Incubator / Local Automation

These are useful on the current workstation, but should be treated as examples until their contracts are hardened:

- `blackboard.py`
- `guild-worker-team.py`
- `obsidian-memory-index.py`
- `build-obsidian-memory-index.ps1`
- `search-obsidian-memory.ps1`
- `build-daily-brief.py`
- `send-daily-brief-home.ps1`
- `send-game-checkin.ps1`
- `mark-game-checkin.ps1`
- `hermes-healthcheck.ps1`

Do not move these scripts while Hermes cron jobs or local shortcuts may still reference their current paths.

## Guild Worker Team Prototype

`guild-worker-team.py` is the tracked incubator launcher for the Guild Worker Team contract. It delegates to the current runtime prototype under `_runtime/flock/`, which reads and writes durable task/artifact state under the Hermes AppData SQLite path by default. Optional Flock source dependencies remain under `_runtime/research/flock/`.

Useful smoke commands:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id smoke-join-chain --include-tasks --include-artifacts --format text
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id smoke-join-chain
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py list-tasks --limit 5
```

JSON remains the default dashboard output for future UI/API consumers. Use `--format text` for human terminal review.

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

## File Discovery

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
