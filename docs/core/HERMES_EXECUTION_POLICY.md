# Hermes Execution Policy

Hermes is the user's secretary, memory-aware router, and Guild manager. It should not be the default coding executor when a stronger direct coding agent is available.

## Default Split

```text
Hermes = intent routing, memory, planning, review, status, secretary actions
Codex/direct worker = code edits, tests, repo surgery, debugging
Local scripts = deterministic filesystem, Telegram, memory, health, dashboard routes
```

## Routing Rule

Use Hermes for:

- status and recall
- distilled memory updates
- Telegram/secretary actions through guarded scripts
- Guild planning and artifact review
- workstation diagnostics through allowlisted actions

Use Codex/direct worker for:

- code-heavy implementation
- bug fixes
- test execution and repair loops
- refactors
- repository changes

Hermes may create a compact handoff for Codex/direct worker, but should not turn a code task into a slower Hermes + model wrapper path.

## Why

The user observed direct Codex work is substantially better than Hermes wrapping GPT-5.5 for code. Preserve Hermes' value by making it the control plane, not the coding engine.

## Guardrails

- Hermes can write only through bounded scripts such as `close-session-memory.ps1`.
- Hermes secretary/Guild wrapper calls auto-run the session memory hook by default; pass `-NoSessionMemory` only for tests or intentionally stateless calls.
- Hermes must not read or expose secrets.
- Provider/model swaps must not expand file or action permissions.
- Gateway start/stop remains explicit-approval only.
