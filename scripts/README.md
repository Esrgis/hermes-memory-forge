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
- `build-daily-brief.py`
- `send-daily-brief-home.ps1`
- `send-game-checkin.ps1`
- `mark-game-checkin.ps1`
- `hermes-healthcheck.ps1`

Do not move these scripts while Hermes cron jobs or local shortcuts may still reference their current paths.
