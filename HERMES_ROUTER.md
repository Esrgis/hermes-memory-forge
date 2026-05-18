# Hermes Bounded Router

Use this file to route routine requests without broad discovery.

Core rule:

- Match the user's intent to a known route.
- Use the known route directly.
- Do not search the filesystem, inspect databases, or load broad skills for routine tasks.
- If no route matches, ask one short question instead of probing.

## Telegram

Triggers:

- `telegram`
- `gửi tôi`
- `nhắn tôi`
- `send me`
- `message me`
- daily greeting / lời chào

Route:

- Use the deterministic workspace script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\send-telegram-home.ps1 -Text "MESSAGE"
```

- Do not inspect `state.db`.
- Do not search for `*telegram*`.
- Do not read `.env`, `auth.json`, or token files.
- Do not use cron.
- Do not start, stop, or inspect the gateway unless the script fails and the user explicitly approves gateway fallback.

For a simple greeting, send one concise Vietnamese message with today's date/time if needed.

## Obsidian

Triggers:

- `obsidian`
- `vault`
- `note`
- `daily`
- `memory`

Route:

- Vault path: `D:\HermesVault\MemoryCore`
- Prefer direct note paths under the vault.
- Do not search outside the vault.
- Do not write raw chat logs.
- Write only distilled markdown.

## Workspace

Triggers:

- `Hermes`
- `workspace`
- `context`
- `memory pipeline`
- `TASKS`

Route:

- Use the current workspace root.
- Read `AGENTS.md`, `PROJECT_CONTEXT.md`, `TASKS.md`, `HERMES_MAP.md`, and this file when present.
- Avoid broad search.

## Coding

Triggers:

- code changes
- tests
- repo
- bug
- refactor

Route:

- Use current default provider `openai-codex` / `gpt-5.5`.
- Delegation is disabled by default.
- Ask before enabling delegation or worktrees.
