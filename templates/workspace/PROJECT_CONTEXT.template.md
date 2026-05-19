# Project Context

This workspace is for building a local-first, memory-aware AI assistant.

## Stack

- Hermes
- Obsidian
- PowerShell
- VSCode
- Everything ES
- Optional model providers: OpenAI Codex, OpenRouter

## Paths

- Workspace: `CHANGE_ME`
- Obsidian vault: `CHANGE_ME`
- Hermes home: `%LOCALAPPDATA%\hermes`

## Operating Rules

- Markdown-first.
- Local-first.
- Prefer bounded retrieval.
- Ask before broad search.
- Avoid generated folders such as `node_modules`, `venv`, caches, and logs.
- Do not expose secrets.
- Do not dump raw chat logs into Obsidian.

## Memory Direction

Use a three-tier memory system:

- Hot memory: compact active facts and procedural quirks.
- Vault living files: stable semantic reference.
- Daily notes: timestamped event stream and audit log.

Memory is semantic compression, not raw storage.

