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

- Vault path: read the local value from `HERMES_MAP.md`.
- Prefer direct note paths under the vault.
- Do not search outside the vault.
- Do not write raw chat logs.
- Write only distilled markdown.

For recall-style questions such as "hôm qua", "lần trước", "nhớ", "vụ X", or "đã làm gì":

- Follow `D:\HermesGuildCore\_obsidian_vault\Specs\Memory Query Protocol Spec.md`.
- Search durable memory with the local Obsidian FTS index when available.
- Use query variants before escalating: original wording, unaccented Vietnamese if relevant, English equivalents, and project/model names.
- Use `session_search` only for session history.
- If the user mentions a prior model, session, handoff, or "vừa nãy/trưa nay/chiều nay" and FTS does not contain the decisive keyword, perform a bounded session-history lookup rather than guessing from vault memory.
- If session lookup finds a durable fact that the vault missed, treat it as a memory-schema gap and distill it into the proper vault note only when memory repair is explicitly requested.
- Do not answer from hot memory alone when the user asks for cross-session recall.
- Report findings first; do not mutate memory or blackboard state unless the user explicitly approved the mutation.

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
- For filename/path discovery, use `scripts/search-files.ps1`; it tries Everything ES first and falls back to scoped `fd`/PowerShell if ES fails.
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
