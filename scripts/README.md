# Scripts

Scripts are split into stable setup helpers and local/incubator automation.

## Stable Setup Helpers

These are intended to be reusable with parameters:

- `setup-workspace.ps1`
- `scaffold-obsidian.ps1`
- `new-daily-note.ps1`
- `set-hermes-profile.ps1`
- `send-telegram-home.ps1`

## Incubator / Local Automation

These are useful on the current workstation, but should be treated as examples until their contracts are hardened:

- `blackboard.py`
- `obsidian-memory-index.py`
- `build-obsidian-memory-index.ps1`
- `search-obsidian-memory.ps1`
- `build-daily-brief.py`
- `send-daily-brief-home.ps1`
- `send-game-checkin.ps1`
- `mark-game-checkin.ps1`
- `hermes-healthcheck.ps1`

Do not move these scripts while Hermes cron jobs or local shortcuts may still reference their current paths.

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
