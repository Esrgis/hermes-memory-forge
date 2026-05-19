---
name: obsidian-rag-check
description: Use for cross-session recall, project memory lookup, "nhớ/hôm qua/lần trước/vụ X" questions, or before changing workspace assumptions. Searches the local Obsidian FTS index before relying on hot memory or guesses.
---

# Obsidian RAG Check

Use this skill when the user asks about past work, previous decisions, durable project context, or any fact likely stored in Obsidian/shared memory.

## Triggers

- "nhớ", "hôm qua", "lần trước", "vụ X", "đã làm gì"
- "check memory", "đọc lại bộ nhớ", "recall", "RAG"
- before risky workspace/config changes that depend on prior constraints
- when hot memory and current context may be stale

## Search First

Run the local Obsidian FTS search:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\search-obsidian-memory.ps1 -Query "QUERY" -Limit 8
```

Use targeted queries with project terms:

```text
HermesGuildCore dangerous operation junction
recall RAG session_search
n8n Flock blackboard
daily brief Hue
```

## How To Use Results

1. Read snippets and note paths.
2. Open only the specific relevant note or section if more context is needed.
3. Use `session_search` only for chat/session history, not durable Obsidian memory.
4. If results conflict with hot memory, state the conflict and prefer the newer durable note unless evidence says otherwise.
5. Do not dump whole notes into the response.

## Mutation Guard

This skill is read-first. It may justify suggestions, but it does not authorize mutation.

Do not delete hot memory, delete blackboard rows, rewrite durable notes, change cron/gateway, or modify workspace paths unless the user explicitly approved that specific mutation.

## If Index Is Missing Or Stale

Check stats:

```powershell
python .\scripts\obsidian-memory-index.py stats
```

If the index is missing or stale and the user asked for recall, ask before rebuilding if it requires access outside the workspace:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-obsidian-memory-index.ps1 -VaultPath D:\HermesVault\MemoryCore
```
