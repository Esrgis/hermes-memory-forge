param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,

    [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'

function Write-Template {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    if ((Test-Path -LiteralPath $Path) -and -not $Overwrite) {
        return
    }

    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

$VaultPath = $VaultPath.TrimEnd('\')
$today = Get-Date -Format 'yyyy-MM-dd'

$folders = @(
    'Daily',
    'System\Assistant\logs',
    'Projects',
    'Concepts',
    'Memory',
    'Specs',
    'Snippets',
    'Runtime',
    'People',
    'Inbox'
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path (Join-Path $VaultPath $folder) | Out-Null
}

Write-Template -Path (Join-Path $VaultPath 'System\Assistant\context.md') -Content @"
# Assistant - Context

Stable operational context for the assistant. Read on demand when decisions need background.

## Operations

- Local-first AI workstation.
- Hermes is the assistant layer.
- Obsidian is long-term markdown memory.

## Active Projects

- Hermes CLI usability.
- Obsidian memory structure.
- Bounded retrieval and tool routing.

## Location & Timezone

- Timezone: Asia/Saigon.

---
Last updated: $today
"@

Write-Template -Path (Join-Path $VaultPath 'System\Assistant\preferences.md') -Content @"
# Assistant - Preferences

Stable user preferences and operating style.

## Communication

- Direct, technical, practical.
- No hype.
- Prefer concise engineering explanations.

## Retrieval

- Prefer bounded discovery.
- Ask before broad search.
- Avoid generated folders such as node_modules, venv, cache, logs.

## Memory

- Do not dump raw chats.
- Distill events into patterns.
- Promote stable patterns into living files.

---
Last updated: $today
"@

Write-Template -Path (Join-Path $VaultPath 'System\Assistant\environment.md') -Content @"
# Assistant - Environment

Hardware, tools, paths, and known issues.

## Key Paths

| Resource | Path |
| --- | --- |
| Vault | $VaultPath |
| Daily notes | $VaultPath\Daily\YYYY-MM-DD.md |
| Hermes home | `%LOCALAPPDATA%\hermes` |

## Tools

- Hermes
- Obsidian
- PowerShell
- Everything ES
- VSCode
- Windows Terminal

## Known Patterns

- Use direct scripts for routine tasks.
- Avoid gateway/cron fallback unless explicitly approved.

---
Last updated: $today
"@

Write-Template -Path (Join-Path $VaultPath 'System\Assistant\logs\issues-fixes-log.md') -Content @"
# Issues & Fixes Log

Append-only record of technical failures and resolutions.

Format:

```text
YYYY-MM-DD HH:mm - Symptom -> Root Cause -> Fix -> Status
```

---
"@

Write-Template -Path (Join-Path $VaultPath 'People\MOC.md') -Content @"
# People - Map of Content

Contacts and relationships.

## Work

- Add work contacts here.

## Personal

- Add personal contacts here.

---
Last updated: $today
"@

Write-Host "Obsidian vault scaffolded at $VaultPath"

