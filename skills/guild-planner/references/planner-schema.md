# Guild Planner Schema Notes

## Accepted Blackboard Task Types

The Worker Team CLI currently accepts:

- `contract`
- `execution`
- `join_review`
- `fix`
- `final_review`

Planner templates may use richer conceptual roles, but server code must normalize them before calling `create-task`.

## Required Track Fields

Each track should provide:

- `id`: short stable label such as `A`
- `title`: human-readable task label
- `task_type`: blackboard-compatible type or a planner-only type that will normalize to `execution`
- `required_rank`: usually `C` or `B`
- `required_skill`: claim-routing skill such as `implementation`, `verification`, `requirements`, `risk-analysis`
- `owner_area`: product/runtime/quality/implementation/review
- `output_file`: simple filename inside quest workspace, no slashes
- `output_artifact`: artifact type published by the worker
- `instruction`: specific bounded worker instruction

## Validation Expectations

- Reject empty track lists.
- Reject duplicated output files.
- Reject output files with path separators.
- Cap execution task count to avoid over-splitting.
- Prefer clear blocked reasons over silent fallback.

## Preview Versus Run

Preview should create no blackboard rows and wake no workers.

Confirm Run may create tasks and call `/api/wake`.
