---
name: obsidian-rag-check
description: Use for cross-session recall, project memory lookup, "nhớ/hôm qua/lần trước/vụ X" questions, or before changing workspace assumptions. Searches the local Obsidian FTS index before relying on hot memory or guesses.
---

# Obsidian RAG Check

Use this skill when the user asks about past work, previous decisions, durable project context, or any fact likely stored in Obsidian/shared memory.

Primary protocol: `D:\HermesGuildCore\_obsidian_vault\Specs\Memory Query Protocol Spec.md`.
Follow that protocol for source tiers, query packets, bounded session-history lookup, metadata repair, and cleanup rules.

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

## Retrieval Ladder

Use this ladder for recall. Do not jump straight to broad filesystem search.

1. Check the current conversation first.
2. Search Obsidian FTS with the user's wording.
3. Search Obsidian FTS with 2-3 query variants:
   - Vietnamese with and without accents when useful.
   - English equivalent terms such as `handoff`, `afternoon`, `deferred analysis`, `current state`.
   - Project terms such as `Hermes`, `Codex`, `GPT-5.4`, `GPT-5.5`, `n8n`, `FTS`.
4. If the user mentions a prior model, session, chat, or handoff and Obsidian does not contain the decisive keyword, do a bounded session-history lookup.
5. If the missing fact is durable, report that the memory schema was missing metadata and add a distilled correction only when the user asked to update memory or the current task is explicitly a memory repair task.

Bounded session-history lookup means:

- Search only known session/history locations from the current tool/runtime, such as Codex or Hermes session indexes.
- Search for exact anchors first: model name, session id, user phrase, date, and handoff terms.
- Do not dump raw chat logs into the response or Obsidian.
- Extract only the minimum evidence needed to answer.

## Required Metadata For Handoffs

Any future handoff or deferred-analysis note should include these fields near the top so lexical search can find it:

```yaml
created_at:
source_model:
target_model:
source_session_hint:
status:
next_action:
retrieval_aliases:
```

`retrieval_aliases` should include the user's natural wording, including Vietnamese phrases when the handoff was discussed in Vietnamese.

## Query Packet Requirement

For non-trivial recall, form a short query packet before searching:

```yaml
intent:
time_anchor:
entities:
source_hint:
target_source:
must_not_search:
queries:
```

This packet can be internal, but the actions should follow it.
Weak models should not invent broad searches when the packet points to a known source tier.

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
