# Agent Profiles v0

These profiles are runtime hints for the Guild Worker Team prototype. They are not personalities.

Machine-readable source: `docs/workers/agent-profiles.json`.

## Roles

| Profile | Rank | Skills | Intended Use |
| --- | --- | --- | --- |
| `hermes-codex` | S | planning, review, orchestration, memory, coding | manager/reviewer while Codex is available |
| `builder` | C | app_logic, ui, fix, general | scoped implementation tasks |
| `tester` | B | testing, qa, general | verification tasks and evidence checks |
| `reviewer` | B | integration_review, review, general | join review and final review tasks |

## Provider Direction

- `hermes-codex` uses Codex as the strong reasoning layer while available.
- `builder`, `tester`, and `reviewer` should be able to run on cheaper/free providers.
- Provider adapters should be swappable: OpenRouter, Gemini, OpenCode, Cerebras.
- The task contract must not depend on one provider.

## Rule

Workers read `WORKER_BOOTSTRAP.md` and the task contract. They do not load broad workspace context by default.
