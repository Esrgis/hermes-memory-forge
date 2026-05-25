# Provider Adapters v0

Provider adapters describe how a worker backend is selected. They must not store secrets.

Machine-readable source: `docs/workers/provider-adapters.json`.

Runtime implementation:

- `scripts/guild_provider_adapters/base.py`: adapter context/result contract.
- `scripts/guild_provider_adapters/local_dry_run.py`: deterministic no-model adapter.
- `scripts/guild_provider_adapters/invalid_output.py`: test-only malformed-output adapter for validation smokes.
- `scripts/guild_provider_adapters/opencode.py`: OpenCode CLI adapter.
- `scripts/guild_provider_adapters/gemini.py`: Gemini direct API adapter with CLI fallback.
- `scripts/guild_provider_adapters/groq.py`: Groq OpenAI-compatible direct API adapter.
- `scripts/guild_provider_adapters/registry.py`: adapter selection and declared-but-unimplemented fallback.
- `scripts/invoke-guild-provider-adapter.ps1`: compatibility wrapper around the Python adapter runtime.
- `scripts/configure-guild-worker.ps1`: framework-style provider selection command that writes `_runtime/guild-worker-agent/provider-selection.json` and can test immediately.

## Contract

Every provider adapter should accept the same worker input:

```json
{
  "agent_profile": {},
  "task_contract": {},
  "bootstrap_path": "docs/workers/WORKER_BOOTSTRAP.md",
  "route_context": []
}
```

Every provider adapter should return an artifact-compatible object:

```json
{
  "ok": true,
  "summary": "short result",
  "files_changed": [],
  "commands_run": [],
  "test_result": "not_run",
  "known_risks": [],
  "blocked_reason": null
}
```

Worker-agent validation:

- `run-guild-worker-agent.ps1` validates `adapter_result.text` after a successful adapter call.
- The text must be valid JSON with `ok`, `summary`, `files_changed`, `commands_run`, `test_result`, `known_risks`, and `blocked_reason`.
- `test_result` must be one of `passed`, `failed`, `not_run`, or `not_required`.
- `files_changed`, `commands_run`, and `known_risks` must be arrays.
- Invalid output is published as a failed artifact with `blocked_reason=invalid_adapter_output` and the task is not marked `done`.
- Adapter/provider failures keep their explicit blocked reason and skip output validation.

## Current Adapter Roles

| Adapter | Kind | Purpose |
| --- | --- | --- |
| `codex` | strong_reasoning | Hermes manager/reviewer while available |
| `gemini` | hosted_model_or_local_cli | Gemini workers through direct API, with CLI fallback |
| `groq` | hosted_model | Groq OpenAI-compatible workers |
| `opencode` | local_cli | terminal/code execution path |
| `cerebras` | hosted_model | fast inference candidate |
| `local-dry-run` | deterministic | smoke tests without model calls |
| `invalid-output-smoke` | test_only | intentionally malformed output for validator smoke tests |

Implemented now:

- `local-dry-run`
- `invalid-output-smoke` for validation smoke tests only
- `opencode`
- `gemini`, using `GEMINI_API_KEY`/`GOOGLE_API_KEY` direct API when available and `gemini` CLI fallback otherwise
- `groq`, using `GROQ_API_KEY`

Declared but not implemented yet:

- `codex`
- `cerebras`

Config command currently exposes only the user-facing worker adapters:

- `opencode`
- `gemini`
- `groq`

`gemini` and `groq` can be selected and smoke-tested through direct hosted-provider adapters. Missing keys return `blocked_reason=provider_missing`.

## Rules

- Do not put API keys in this repo.
- Read provider secrets from the user's existing provider configuration only through approved scripts.
- If provider configuration is missing, publish a blocked artifact instead of guessing.
- A provider error should not mark the task done.
- Model output is not evidence by itself; commands/tests/artifacts are evidence.
- For opencode, prefer `opencode run --pure --format json` for non-interactive worker calls. Initial smoke tests on 2026-05-21 worked, but even tiny prompts loaded roughly 13k input tokens.
- Gemini does not require the CLI when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is present; the adapter calls the OpenAI-compatible REST endpoint directly. CLI fallback is only for local authenticated Gemini CLI sessions.
- Groq expects `GROQ_API_KEY` in the environment. Use `GROQ_MODEL` or `-Model` to override the default model.
