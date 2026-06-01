# Architecture Summary

## Big Picture

HermesGuildCore là một local-first assistant/workflow prototype.

Mục tiêu dài hạn:

```text
local-first personal cognitive OS
+ semantic memory
+ blackboard runtime
+ deterministic scripts
+ bounded agent/workflow orchestration
```

Không phải:

- production SaaS
- fully autonomous AI company
- replacement cho n8n/Obsidian/Hermes
- TikTok autoposter hoàn chỉnh

## Main Layers

```text
User
-> Terminal / Telegram / Dashboard
-> Hermes router
-> Deterministic scripts / n8n workflows / Guild runtime
-> SQLite runtime state
-> Artifacts/files
-> Obsidian distilled memory
```

## Memory Boundary

Obsidian:

- durable semantic memory
- daily notes
- project decisions
- architecture notes
- distilled lessons

Không dùng Obsidian cho:

- live queue
- raw chat logs
- binary artifacts
- secret storage

SQLite/AppData:

- runtime queue
- task status
- artifact metadata
- approval state
- current operational state

`_runtime/`:

- scratch
- logs
- exported JSON
- local artifacts
- cloned research repos
- installed local n8n runner

## Guild Runtime

Guild Runtime v0 contract:

```text
human-approved DAG
+ artifact blackboard
+ automatic claim
+ join review
+ bounded fix loops
```

Implemented pieces:

- task schema
- artifact schema
- dependency unlock
- claim/lease/heartbeat
- fake worker
- provider-backed worker wrapper
- output validation
- dashboard
- visible worker terminals

Still bridge/prototype:

- finalization still partly API-owned
- scheduler v1 is simple
- event log is derived
- real provider reliability varies
- not production orchestration

## n8n Boundary

n8n should handle:

- schedule/cron
- simple orchestration
- Telegram notification
- queue trigger
- approval callback workflow
- retry/light plumbing

n8n should not handle:

- deep reasoning
- style memory
- ambiguous content decisions
- agent planning
- large prompt logic

Hermes/local scripts should handle:

- reasoning
- content generation
- memory/style consistency
- decision logic

## Content Factory MVP Boundary

Content Factory MVP intentionally avoids full Guild runtime.

Chosen architecture:

```text
n8n = orchestrator
Hermes/local script = content brain
SQLite = content job state
Obsidian = long-term style memory
Telegram = human approval gate
```

Status flow:

```text
idea_pending
-> script_done
-> render_done
-> approval_pending
-> approved | rejected
```

No auto-post in v0.

## What Is Actually Working

Working:

- local content factory CLI
- SQLite content jobs under AppData
- artifact files under `_runtime/content-factory`
- Telegram send via existing route
- n8n local install/start/import
- n8n UI accessible
- Guild blackboard prototype smokes
- local/fake worker and provider adapter smokes

Not yet working / not done:

- production TikTok/YouTube posting
- real TTS/render pipeline
- trend discovery
- durable event table for content factory
- n8n approval callback fully wired/tested with live Telegram Trigger
- final Guild v2 worker-owned finalization

## Practical Lesson

The most useful pattern was not "many AI agents talking".

The useful pattern was:

```text
clear state
+ bounded tasks
+ explicit artifacts
+ validation
+ human approval
+ deterministic fallbacks
```

