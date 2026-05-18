# Hermes Memory Forge

A Windows-first template for turning Hermes into a local-first, memory-aware AI workstation.

This is not a chatbot wrapper. It is a small reproducible setup for:

- bounded tool routing
- markdown-first memory
- Obsidian as a long-term knowledge substrate
- Hermes hot memory and sessions as runtime context
- quota-aware daily assistant workflows
- future blackboard and orchestration experiments

## What This Gives You

- Workspace control files: `AGENTS.md`, `HERMES_ROUTER.md`, `MEMORY_PIPELINE.md`
- Obsidian vault scaffold under `System/Assistant/`, `Daily/`, `People/`, etc.
- PowerShell scripts for setup, vault scaffolding, Hermes links, and Telegram quick-send
- A cognitive architecture direction that treats memory as semantic compression, not raw storage

## Requirements

- Windows
- PowerShell 7 recommended
- Hermes installed and working
- Obsidian installed separately
- Optional: Everything CLI `es.exe`
- Optional: Telegram configured in Hermes `.env`

## Quick Start

From this folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-workspace.ps1 -WorkspacePath "D:\TuanKeCuoi" -VaultPath "D:\HermesVault\MemoryCore"
```

For a new machine, copy the template files first:

```powershell
Copy-Item .\PROJECT_CONTEXT.template.md .\PROJECT_CONTEXT.md
Copy-Item .\TASKS.template.md .\TASKS.md
Copy-Item .\HERMES_MAP.template.md .\HERMES_MAP.md
```

Scaffold the Obsidian vault:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\scaffold-obsidian.ps1 -VaultPath "D:\HermesVault\MemoryCore"
```

Set Hermes to a lean daily profile:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\set-hermes-profile.ps1 -Profile codex-today
```

## Profiles

`codex-today`

- provider: `openai-codex`
- model: `gpt-5.5`
- disables delegation and MoA

`openrouter-lean`

- provider: `openrouter`
- model: `nvidia/nemotron-3-super-120b-a12b:free`
- disables delegation and MoA

## Daily Usage

Classic Hermes:

```powershell
hermes chat
```

TUI:

```powershell
hermes chat --tui
```

Quick Telegram send:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\send-telegram-home.ps1 -Text "Hello from Hermes"
```

## Core Principle

Memory is not a database.

Useful assistant memory is:

- abstraction
- prioritization
- retrieval
- forgetting
- synthesis
- conflict resolution

Raw logs are not memory. They are inputs to memory.

## Repository Hygiene

Do not commit:

- `_hermes/`
- `_runtime/`
- `_obsidian_vault`
- `.env`
- auth files
- tokens
- private vault content unless intentionally sanitized

## Suggested Repo Name

`hermes-memory-forge`

The current local folder can be renamed to that when no shell/process is using it.

