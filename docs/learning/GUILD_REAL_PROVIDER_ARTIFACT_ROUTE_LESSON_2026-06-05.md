# Guild Real Provider Artifact Route Lesson - 2026-06-05

## Trigger

A real-provider Guild run reaches a worker provider successfully, but the task fails with `invalid_adapter_output` and no workspace file is written.

## Evidence

- Quest: `quest-manual-dashboard-task-20260605141838`
- Failed worker: `worker-c`
- Provider route: `openrouter:poolside-laguna-free`
- Provider attempt completed, but the returned text was prose/tool-call style rather than compact artifact JSON.
- Runtime expected a Guild artifact JSON object, so validation failed before `verification.md` could be written.
- The reviewer stayed blocked because the verification dependency did not complete.

## Rule

Artifact-worker ladders must include only providers/models that reliably return the Guild worker artifact schema. A model that emits tool-call/prose output should not be used for `code-edit-worker` or `join-review-worker` unless an adapter translates that output into validated artifact JSON.

## Current Guardrail

- `openrouter:poolside-laguna-free` is excluded from the default artifact worker and review ladders.
- A no-provider fixture test rejects Poolside-style `<tool_call>` output as non-artifact output.
- Requests that explicitly require `build-1.md`, `build-2.md`, and `build-3.md` should select the `three-part-local-demo` template instead of the generic `standard-build` template.

## Limitation

This note documents a routing/contract guardrail. It does not prove full real-provider E2E success until a fresh quest creates the expected worker files, review files, and final artifact on disk.
