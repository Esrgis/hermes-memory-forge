# Packaging Checklist

Use this before treating the repo as a downloadable Hermes customization package.

## Repo Hygiene

- `git status --short` is understood.
- Local runtime folders are ignored.
- Private files are ignored or templated.
- No secrets, tokens, auth files, raw chat logs, or private vault content are in the diff.
- Machine-specific paths are either removed, parameterized, or explicitly marked as examples.

## Installer Shape

Target commands:

```powershell
.\scripts\doctor.ps1
.\scripts\setup-workspace.ps1 -WorkspacePath <path> -VaultPath <path>
.\scripts\set-hermes-profile.ps1 -Profile <profile>
.\scripts\repair.ps1 -WhatIf
```

Current state:

- `setup-workspace.ps1` exists.
- `scaffold-obsidian.ps1` exists.
- `set-hermes-profile.ps1` exists.
- `doctor.ps1` does not exist yet.
- `repair.ps1` does not exist yet.
- `obsidian-memory-index.py` exists as a local FTS5 recall MVP.

## Hermes Behavior

The package should:

- detect whether `hermes` is available
- show the detected Hermes home
- verify config readability
- apply profiles only after making the intended changes clear
- avoid overwriting existing user config without backup or confirmation

The package should not:

- install Hermes silently
- modify secrets
- enable cron/gateway/delegation/MoA by default
- assume Telegram is configured
- assume one user's Obsidian vault path

## Multi-Agent Readiness

Do not present multi-agent behavior as stable until these contracts exist:

- blackboard schema versioning
- task claim/release state transitions
- worker output format
- permission levels enforced in task records
- deterministic smoke test
- rollback/failure handling
- clear boundary between Hermes coordinator and worker execution

## Recall/RAG Readiness

- Obsidian FTS index can build from a vault path.
- Search returns snippets and note paths without dumping the vault.
- Runtime index is outside the vault.
- Recall jobs are report-only unless mutation is explicitly approved.
- Auxiliary `session_search` provider/model is configured to a fast reliable summarizer, or summaries are treated as optional.
