---
name: guild-planner
description: Use when designing, reviewing, or improving Hermes Guild task decomposition, plan preview, worker skill mapping, dependency graphs, join_review, fix loops, or planner skill-pack behavior.
---

# Guild Planner

Use this skill to turn one user request into a bounded Guild quest plan.

## Core Workflow

1. Classify the request:
   - build/feature
   - debug/fix
   - provider/runtime config
   - refactor
   - docs/release
   - tiny one-worker task
2. Choose the smallest useful task graph.
3. Prefer `Preview Plan` before worker wake.
4. Assign task types accepted by the blackboard: `contract`, `execution`, `join_review`, `fix`, `final_review`.
5. Preserve intent with `required_skill`, `owner_area`, title, output artifact, and request text.
6. Add `join_review` only when fan-in is meaningful.
7. Add fix loops only after evidence shows a mismatch, failed task, or missing expected file.

## Hard Rules

- Do not split tiny work just to use every worker.
- Do not hardcode provider/model by worker identity.
- Keep provider selection as capability ammo.
- Every worker task must have:
  - `output_file`
  - `output_artifact`
  - `required_skill`
  - concrete evidence or verification expectation
- Never expose secrets in planner text, task requests, logs, or memory.
- Do not wake workers from a preview-only request.
- If the user has not explicitly asked to run a demo/UI, do not open UI or start dashboard servers.

## Task Graph Patterns

- Build: `contract -> execution -> verification -> join_review`
- Debug: `reproduce -> root cause -> patch -> join_review`
- Provider/config: `map config -> apply config -> smoke route -> join_review`
- Refactor: `impact map -> edit -> regression verify -> join_review`
- Tiny task: `execution -> join_review` or just `execution` if review adds no value

Map planner-only labels such as `analysis`, `verification`, `reproduce`, or `patch` to blackboard `execution`; keep the semantic role in `required_skill`, `title`, and `output_artifact`.

## References

Read `references/planner-schema.md` when editing `config/guild/planner-skills.json` or server-side planner validation.
