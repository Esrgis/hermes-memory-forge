# Hermes Memory Forge

A Windows-first template for turning Hermes into a local-first, memory-aware AI workstation.

This is not a chatbot wrapper. It is a small reproducible setup for:

- bounded tool routing
- markdown-first memory
- Obsidian as a long-term knowledge substrate
- Hermes hot memory and sessions as runtime context
- quota-aware daily assistant workflows
- optional blackboard and orchestration experiments

## What This Gives You

- Workspace control files: `AGENTS.md`, `docs/core/HERMES_ROUTER.md`, `docs/core/MEMORY_PIPELINE.md`
- Obsidian vault scaffold under `System/Assistant/`, `Daily/`, `People/`, etc.
- PowerShell scripts for setup, vault scaffolding, Hermes links, and Telegram quick-send
- A cognitive architecture direction that treats memory as semantic compression, not raw storage

## What This Is Not Yet

- A Hermes installer.
- A full config repair tool.
- A finished multi-agent framework.
- A replacement for Hermes, Obsidian, Codex, n8n, or Flock.

The current package assumes Hermes already exists. It can prepare a workspace around Hermes, apply a small profile, scaffold memory folders, and provide optional automation examples.

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
$workspace = (Get-Location).Path
$vault = "D:\Path\To\MemoryCore"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-workspace.ps1 -WorkspacePath $workspace -VaultPath $vault
```

For a new machine, copy the template files first:

```powershell
Copy-Item .\templates\workspace\PROJECT_CONTEXT.template.md .\PROJECT_CONTEXT.md
Copy-Item .\templates\workspace\TASKS.template.md .\TASKS.md
Copy-Item .\templates\workspace\HERMES_MAP.template.md .\HERMES_MAP.md
```

Scaffold the Obsidian vault:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\scaffold-obsidian.ps1 -VaultPath $vault
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

For the full system direction, read:

- `docs/architecture/COGNITIVE_ARCHITECTURE.md`
- `docs/architecture/HERMES_COGNITIVE_OS_BLUEPRINT.md`
- `docs/architecture/HERMES_GUILD_SYSTEM_THOUGHTS.md`

These documents describe the intended memory architecture and future multi-agent direction. They are design documents, not a finished runtime contract.

## Repo Boundaries

Keep these layers separate:

- Public template: setup scripts, templates, docs, and safe defaults.
- Local runtime: `_runtime/`, `_hermes/`, `_obsidian_vault`, local config, logs, and SQLite state.
- Incubator: blackboard, daily automation, health checks, and future orchestration experiments.

Local runtime files should not be committed. Optional incubator scripts should be treated as examples until they have stable inputs, outputs, dry-run behavior, and tests.

## Repository Hygiene

Do not commit:

- `_hermes/`
- `_runtime/`
- `_obsidian_vault`
- `.env`
- auth files
- tokens
- private vault content unless intentionally sanitized

Before publishing or opening a PR:

1. Run `git status --short`.
2. Check for machine-specific paths.
3. Check for secrets or auth files.
4. Keep local automation separate from reusable template behavior.

## Suggested Repo Name

`hermes-memory-forge`

The current local folder can be renamed to that when no shell/process is using it.
