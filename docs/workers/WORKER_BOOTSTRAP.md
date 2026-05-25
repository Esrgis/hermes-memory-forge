# Worker Bootstrap v0

Purpose: give weak/model-backed Guild workers a short route map. Do not load the whole workspace into a worker prompt.

## Always

1. Read the current task contract first.
2. Read only the route files required by the task type and risk level.
3. Do not broad search. Use bounded scripts.
4. Do not read secrets, `.env`, auth files, browser profiles, or token stores.
5. Do not edit outside `allowed_files`.
6. Do not touch `forbidden_files`.
7. If evidence is missing, stop and publish a blocked/needs-info artifact instead of guessing.
8. Output a structured artifact with summary, files changed, commands run, tests, and known risks.

## Route Table

| Trigger | Read | Action |
| --- | --- | --- |
| any task | `START_HERE.md`, this file, task contract | obey workspace routes and task scope |
| file discovery | `scripts/README.md` Searchable Workspace | use `scripts/search-files.ps1` |
| content search | `scripts/README.md` Searchable Workspace | use `scripts/search-content.ps1` |
| file preview | `scripts/README.md` Searchable Workspace | use `scripts/preview-file.ps1` |
| coding/edit task | `docs/core/HERMES_ROUTER.md`, task `allowed_files` | edit only scoped files, then run declared tests |
| UI task | task acceptance criteria, relevant UI file, local design notes | keep changes focused and test render path |
| memory/recall | `skills/obsidian-rag-check/SKILL.md`, `_obsidian_vault/Specs/Memory Query Protocol Spec.md` | search durable memory before answering |
| destructive/path-sensitive | `skills/dangerous-operation-guard/SKILL.md` | stop unless explicitly approved |
| join/review | `_obsidian_vault/Specs/Guild Task Contract Spec.md` | read upstream artifacts, decide accept/revise, create bounded follow-up |
| provider/tool failure | task contract, provider profile | publish evidence and stop after bounded retry |

## Minimal Working Loop

```text
load agent profile
-> claim one eligible task
-> read Worker Bootstrap v0
-> read task contract
-> read only route-specific docs
-> do scoped work
-> run declared validation
-> publish artifact
-> mark task done only if evidence is complete
```

## Artifact Shape

Workers should publish this information even if the backend model is weak:

```json
{
  "ok": true,
  "task_id": "task-id",
  "producer_agent_id": "agent-id",
  "summary": "short result",
  "files_changed": [],
  "commands_run": [],
  "test_result": "passed|failed|not_run|not_required",
  "known_risks": [],
  "blocked_reason": null
}
```

Use `ok: false` and a concrete `blocked_reason` when the worker cannot proceed safely.
