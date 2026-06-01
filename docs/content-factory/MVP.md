# Content Factory MVP

This is a deliberately small local-first pipeline for TikTok/Shorts candidates.

## Roles

```text
n8n = schedule, orchestration, Telegram approval plumbing
Hermes/local script = content reasoning and generation
SQLite = runtime queue and approval state
Obsidian = durable style memory after patterns are distilled
```

Do not use the full Guild worker runtime for this MVP. A short video pipeline is mostly sequential and approval-driven.

## Local State

Default runtime paths:

```text
%LOCALAPPDATA%/hermes/content-factory/content_factory.sqlite
_runtime/content-factory/runs/<job_id>/
```

SQLite lives under AppData because this workstation has known SQLite I/O issues under workspace `_runtime`. Artifact files stay under ignored workspace runtime folders.

## Status Flow

```text
idea_pending
-> script_done
-> render_done
-> approval_pending
-> approved | rejected
```

No TikTok/YouTube auto-posting in v0.

## CLI Contract

Initialize:

```powershell
python .\scripts\content_factory.py init --json
```

Create a job:

```powershell
python .\scripts\content_factory.py create-job --topic "AI workflow" --niche "local-first automation" --language vi --json
```

Generate script and caption:

```powershell
python .\scripts\content_factory.py generate-script --job-id JOB_ID --json
```

Create a placeholder video artifact:

```powershell
python .\scripts\content_factory.py render-placeholder --job-id JOB_ID --json
```

Build approval message without sending:

```powershell
python .\scripts\content_factory.py approval-message --job-id JOB_ID --set-pending
```

Send approval through the existing Telegram route:

```powershell
python .\scripts\content_factory.py send-approval --job-id JOB_ID --json
```

Dry-run Telegram send:

```powershell
python .\scripts\content_factory.py send-approval --job-id JOB_ID --dry-run --json
```

Record decision:

```powershell
python .\scripts\content_factory.py mark-decision --job-id JOB_ID --decision approved --json
python .\scripts\content_factory.py mark-decision --job-id JOB_ID --decision rejected --reason "hook weak" --json
```

Inspect:

```powershell
python .\scripts\content_factory.py show-job --job-id JOB_ID
python .\scripts\content_factory.py list-jobs
```

## n8n MVP Shape

Workflow A: candidate generation

```text
Manual Trigger or Schedule Trigger
-> Execute Command: create-job
-> Execute Command: generate-script
-> Execute Command: render-placeholder
-> Execute Command: send-approval
```

Workflow B: approval handler

```text
Telegram Trigger
-> If message starts with /approve or /reject
-> Execute Command: mark-decision
```

The sample JSON files live in `docs/content-factory/n8n/`.

Use the dry-run candidate workflow first:

```text
docs/content-factory/n8n/content-factory-candidate.workflow.json
```

After dry-run works, switch to the real Telegram variant:

```text
docs/content-factory/n8n/content-factory-candidate-real-telegram.workflow.json
```

The real Telegram variant still uses `Execute Command` and `scripts/send-telegram-home.ps1`, so it does not require a separate n8n Telegram credential for sending approval previews.

## Build Boundary

Add TTS and real video rendering only after this approval loop works reliably:

```text
job created
artifacts written
Telegram preview sent
approve/reject stored
```
