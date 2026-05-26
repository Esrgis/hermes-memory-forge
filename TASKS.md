# Tasks

## Active

- [x] Prototype Flock Worker Team under `_runtime/flock/`.
- [x] Validate Flock on Windows/Python 3.12+ without production integration.
- [x] Test whether Flock can use deterministic/fake workers before paid model calls.
- [x] Define Guild Task Contract v0 with rank, leases, quest chains, and artifact join tasks.
- [x] Implement concrete Guild Task Contract fields in the Flock Worker Team prototype.
- [x] Add concrete plan-review, evidence, and stop-condition fields to the Flock Worker Team prototype.
- [x] Add a small CLI/API route to create/list/inspect Worker Team tasks.
- [x] Add DAG unlock rules so workers only claim dependency-ready `open` tasks.
- [x] Add atomic rank-based claim and lease/heartbeat.
- [x] Add `join_review` support that reads artifacts and can propose bounded fix tasks.
- [x] Decide the data contract between Guild Dashboard and Worker Team state.
- [x] Add a tiny human-readable terminal dashboard view.
- [x] Add a simple static Guild Dashboard UI for loading dashboard JSON.
- [x] Refactor static Guild Dashboard UI into a four-column Blackboard board.
- [x] Add a deterministic/fake worker loop before any model-backed workers.
- [x] Add reset/seed and tick scripts for a minimal dashboard control loop.
- [x] Create Worker Bootstrap v0 for weak/model-backed workers.
- [x] Create Agent Profiles v0 for Hermes, Builder, Tester, and Reviewer.
- [x] Add Provider Adapter v0 shape for Codex, OpenRouter, Gemini, OpenCode, Cerebras, and local dry-run.
- [x] Add first real worker-agent loop that claims tasks, calls a provider adapter, publishes artifacts, sets status, and unlocks dependents.
- [x] Add Hermes dispatch route that sets a specific task Ready and wakes opencode to self-claim it.
- [x] Add framework-style worker provider config command with agent/adapter/provider/model selection and `-TestNow`.
- [x] Add adapter output validation before worker-agent marks tasks done.
- [x] Add invalid-output smoke adapter to prove malformed provider output is blocked.
- [x] Add local Guild Dashboard API server and UI task assignment panel for manual quest creation.
- [x] Add dashboard wake route that launches worker terminal loop through the UI path.
- [x] Simplify dashboard flow to one user-facing button: `Giao Task Cho Hermes`, with automatic worker wake after quest creation.
- [x] Add a Vietnamese crash-course doc explaining the Guild Runtime architecture and senior design decisions.
- [x] Expand the crash-course doc into a code-reading curriculum with UI/API/worker/adapter walkthroughs, library notes, smoke-test workflow, and senior debugging loop.
- [x] Add low-context handoff for continuing the UI Guild demo in a fresh window.
- [x] Add Guild Dashboard Provider Lab for saving local provider keys, listing models, selecting ammo, and running Test Now.
- [ ] Keep n8n as Daily Team runtime, not Worker Team runtime.

## Findings

- 2026-05-20: Created `_runtime/flock/worker_team_prototype.py`.
- 2026-05-20: Flock deterministic custom engines worked with Python 3.13 through `_runtime/research/flock/.venv`.
- 2026-05-20: In-memory prototype produced `GuildTask -> ImplementationResult/TestResult/ReviewResult -> TaskDecision`.
- 2026-05-20: Workspace-local SQLite under `_runtime/flock/` failed with `sqlite3.OperationalError: disk I/O error`, including a minimal sqlite smoke test. Treat this as an environment/storage gate, not a Flock orchestration failure.
- 2026-05-20: Durable Flock SQLite works under `C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite`.
- 2026-05-20: Guild meetings are modeled as `join_review` tasks that read upstream artifacts, not as meetings between specific worker agents.
- 2026-05-20: Flock prototype now emits `TaskDecision(task_type=join_review, output_artifact=integration_report)` with `quest_chain_id` and task contract fields.
- 2026-05-20: Guild Runtime v0 is explicitly constrained to human-approved DAG, artifact blackboard, automatic claim, join review, and bounded fix loops.
- 2026-05-20: Flock prototype task schema now includes plan review gate fields, owner area, status, definition of done, test command, style guide, required evidence, and stop-condition limits.
- 2026-05-20: Smoke test passed with durable AppData SQLite; `TaskDecision` accepted only after `test_passed`, `review_approved`, and `evidence_complete` were true.
- 2026-05-20: Added durable `guild_tasks` queue table in the Worker Team SQLite and CLI commands: `create-task`, `list-tasks`, `inspect-task`, plus `run-demo`.
- 2026-05-20: CLI smoke task `smoke-cli-task` was created, listed, and inspected successfully under quest chain `smoke-cli-chain`.
- 2026-05-20: Added `unlock-ready` DAG gate command and `set-status` smoke helper.
- 2026-05-20: DAG unlock smoke passed: `smoke-unlock-t1` opened only after dependency `smoke-unlock-t0` was `done` and plan review was approved; `smoke-cli-task` remained blocked because plan review was pending.
- 2026-05-20: Added `claim-next`, `heartbeat`, and `release-expired` commands with claim fields `assignee_id`, `claimed_at`, `lease_until`, `claim_attempt`, and `heartbeat_at`.
- 2026-05-20: Rank claim smoke passed: rank C worker was rejected for rank B tasks; rank B worker claimed `smoke-unlock-t1` with a lease and heartbeat extended it.
- 2026-05-20: Lease release smoke passed: expired claim by `worker-expired` was released back to `open`.
- 2026-05-20: Added durable `guild_artifacts` table and CLI commands `publish-artifact`, `list-artifacts`, and `run-join-review`.
- 2026-05-20: Queued join-review smoke passed: backend artifact was OK, frontend artifact had mismatch, `run-join-review` emitted `decision=revise`, published a `task_decision` artifact, and generated `smoke-join-review-fix-1` as a blocked fix task pending plan review.
- 2026-05-20: Added `dashboard` read command with `schema_version=guild_dashboard_read_v0`, returning task/artifact counts, status/type counts, chain summaries, open tasks, blocked review tasks, and optional full task/artifact rows.
- 2026-05-20: Added `dashboard --format text` for terminal-readable Guild Dashboard output while preserving JSON as the default read contract.
- 2026-05-20: Disabled the auto-skill cron experiment by pausing `monitor-tool-calls`, backing up the injected `writing-plans` hook and monitor script, and replacing them with inert safety markers.
- 2026-05-20: Copied raw Hermes/Gemini handoff notes into `_runtime/notes/`; root copies could not be removed because Windows returned access denied, so `.gitignore` now excludes those filenames.
- 2026-05-20: Added static incubator UI `docs/incubation/guild-dashboard.html` and export route `scripts/export-guild-dashboard.ps1`.
- 2026-05-20: Created demo blackboard chain `demo-even-random-app`: spec done, app logic/UI open, tester/join review blocked by dependencies.
- 2026-05-20: User prefers the dashboard to be framed as a Blackboard with four columns: unclaimed/ready, claimed/in-progress by agent, blocked/waiting, and done/artifacts published.
- 2026-05-21: Refactored `docs/incubation/guild-dashboard.html` into a StudioBinder-inspired four-column Blackboard view: Ready, Claimed, Blocked, Done.
- 2026-05-21: Added `run-fake-worker` to `_runtime/flock/worker_team_prototype.py`. It claims open tasks, publishes deterministic artifacts, marks tasks done, unlocks dependency-ready tasks, and runs `join_review` tasks.
- 2026-05-21: Fake worker smoke passed on `smoke-fake-loop`: execution task completed, join review unlocked, artifact lookup by `artifact_type` worked, decision accepted, final dashboard showed all tasks `done`.
- 2026-05-21: Demo chain `demo-even-random-app` was advanced by `fake-demo-worker`; all five tasks are now `done` and four artifacts are published.
- 2026-05-21: Added `seed-demo-chain`, `scripts/tick-guild-dashboard.ps1`, `scripts/open-guild-dashboard.ps1 -Reset`, and dashboard Refresh/Auto controls. End-to-end smoke passed: reset demo, tick worker, export JSON, and localhost dashboard JSON fetch returned HTTP 200.
- 2026-05-21: Updated dashboard JSON and UI semantics: cards now expose `claimed_at`, `heartbeat_at`, dependency IDs, human gate flag, generated/fix metadata, and `block_reason`; the card meter represents task hold/lease time instead of chain progress.
- 2026-05-21: Dashboard agent strip now represents four fixed roles: Hermes, Builder, Tester, and Reviewer. Task cards show tags for task type, rank, skill, generated tasks, human gate, plan gate, artifact, and block reason.
- 2026-05-21: Added `scripts/start-guild-worker-terminal.ps1` to launch a visible terminal-backed worker loop for a selected agent profile.
- 2026-05-21: Clarified current Flock usage: the live dashboard/control commands are mostly Pydantic + SQLite + scripts, while Flock is still the typed orchestration proof-of-concept and Worker Team runtime candidate.
- 2026-05-21: Added Worker Bootstrap v0 under `docs/workers/WORKER_BOOTSTRAP.md`, human/machine-readable agent profiles under `docs/workers/`, and `scripts/get-guild-agent-profile.ps1`.
- 2026-05-21: Updated `scripts/start-guild-worker-terminal.ps1` to accept `-Profile` and added `-DryRun`; parse/profile smoke passed for `builder` and `tester`.
- 2026-05-21: Added Provider Adapters v0 under `docs/workers/PROVIDER_ADAPTERS.md` and `docs/workers/provider-adapters.json`, plus `scripts/get-guild-provider-adapter.ps1`; adapter smoke passed for `local-dry-run` and `opencode`.
- 2026-05-21: Direct `opencode run --format json` smoke succeeded and returned exact JSON without file edits. In the Codex sandbox, opencode needs escalation because it spawns `git`; tiny prompts still loaded roughly 13k input tokens, even with `--pure`.
- 2026-05-21: Added `scripts/invoke-guild-provider-adapter.ps1`; `local-dry-run` and `opencode` adapter invocations work, with opencode using `opencode run --pure --format json`.
- 2026-05-21: Added `scripts/run-guild-worker-agent.ps1`, plus `claim-next --quest-chain-id` and `publish-artifact --payload-json-file`. The script claims a task, builds a bounded prompt packet, calls a provider adapter, publishes an artifact, sets task status, and unlocks dependents.
- 2026-05-21: Real worker-agent smoke passed with `local-dry-run`: `builder` completed app logic and UI tasks, `tester` completed the test task, `reviewer` completed the join review task, and dashboard export showed demo chain `done=5` with four artifacts.
- 2026-05-21: Added `claim-next --task-id`, `scripts/invoke-hermes-opencode-task.ps1`, and a Hermes-dispatch flow: Hermes profile inspects a task, sets that exact task to `open`, then wakes `builder` with `opencode` so it self-claims by `task_id`.
- 2026-05-21: Hermes -> opencode smoke passed on `smoke-hermes-opencode-agent`: task moved to Ready, opencode returned artifact JSON, artifact `artifact-52eb6a34` was published, task was marked `done`, and dashboard export for `demo-hermes-opencode-handoff` showed `done=1`, `artifacts=1`. Git status showed no unexpected file edits from opencode.
- 2026-05-21: Added visible worker wake mode to `scripts/invoke-hermes-opencode-task.ps1`; it writes a runtime PowerShell script, transcript log, and result JSON under `_runtime/guild-worker-agent/`.
- 2026-05-21: Visible local dry-run worker smoke passed after replacing brittle `$LASTEXITCODE` checks for PowerShell child scripts with null-output checks.
- 2026-05-21: Visible Hermes -> opencode worker smoke passed on `smoke-visible-opencode-agent-v1`: a terminal window ran `builder/opencode`, artifact `artifact-4402fc37` was published, task marked `done`, dashboard export showed `done=1`, `artifacts=1`, and opencode reported ~14k total tokens with no file edits.
- 2026-05-21: Added project-local `opencode.json` with a `9router` OpenAI-compatible provider and `opencode-9router` provider adapter. 9Router is installed (`0.4.59`), reachable at `127.0.0.1:20128`, and exposes models including `openrouter/qwen/qwen3-coder:free`.
- 2026-05-21: `opencode models 9router` works after project config, but request smoke is blocked by 9Router auth (`401 Missing/Invalid API key`). Config now references `{env:NINE_ROUTER_API_KEY}` instead of hardcoding a dummy key, and adapter correctly returns `blocked_reason=provider_error_event`.
- 2026-05-22: Split provider adapter logic into Python runtime modules under `scripts/guild_provider_adapters/`, keeping `scripts/invoke-guild-provider-adapter.ps1` as a compatibility wrapper.
- 2026-05-22: Added `scripts/configure-guild-worker.ps1` to select `Profile`, user-facing `Adapter` (`opencode`, `openrouter`, `gemini`), optional `Provider`/`Model`, write `_runtime/guild-worker-agent/provider-selection.json`, and run `-TestNow`.
- 2026-05-22: `opencode` adapter supports `-Provider`/`-Model` routing; `-Provider 9router -Model openrouter/qwen/qwen3-coder:free` reaches the local 9Router/OpenRouter path but is blocked by provider auth (`401 User not found`).
- 2026-05-22: `configure-guild-worker.ps1 -Profile builder -Adapter opencode -TestNow` passes outside the Codex sandbox and returns `{"ok":true}`; inside the sandbox it can fail with the known `uv_spawn 'git'` permission error.
- 2026-05-22: `openrouter` and `gemini` are selectable in the config command but direct runtime adapters are not implemented yet; they return `blocked_reason=adapter_not_implemented`.
- 2026-05-22: `run-guild-worker-agent.ps1 -UseConfiguredProvider` can read the saved provider selection and use it for worker claims.
- 2026-05-22: Added worker-agent validation of `adapter_result.text`. Successful adapters must return artifact JSON with `ok`, `summary`, `files_changed`, `commands_run`, `test_result`, `known_risks`, and `blocked_reason`; invalid output blocks completion with `invalid_adapter_output`.
- 2026-05-22: Local dry-run validation smoke passed on `smoke-visible-local-agent-v2`: artifact `artifact-685ef6bc` includes `adapter_output_validation.valid=true` and `worker_output`, and the task was marked `done`.
- 2026-05-22: Added `invalid-output-smoke` test-only adapter. Negative validation smoke passed on `smoke-invalid-output-agent-v1`: artifact `artifact-55929137` captured missing required fields, `blocked_reason=invalid_adapter_output`, and the task was marked `failed`.
- 2026-05-22: Added `scripts/guild-dashboard-server.py` with local API routes `/api/health`, `/api/dashboard`, `/api/quest/manual`, and `/api/wake`. Updated `scripts/open-guild-dashboard.ps1` to launch this API server instead of plain `python -m http.server`.
- 2026-05-22: Updated `docs/incubation/guild-dashboard.html` with a first-class UI task panel: title, request, allowed files, adapter, Assign Task, Wake Workers, and a Hermes Planning Log that shows progress summaries rather than hidden chain-of-thought.
- 2026-05-22: Manual UI quest API smoke passed on `quest-ui-smoke-quest-2`: the server created a 4-task chain (`spec`, `build`, `test`, `review`), unlocked build to `open`, and returned dashboard JSON with 1 done, 1 open, and 2 blocked tasks.
- 2026-05-22: Wake API dry-run smoke passed for `quest-ui-smoke-quest-2` and `builder/local-dry-run`; it called `scripts/start-guild-worker-terminal.ps1` successfully without opening a terminal in the smoke test.
- 2026-05-22: Dashboard UI now has one main user action, `Giao Task Cho Hermes`; it calls `/api/quest/manual` and then automatically calls `/api/wake`. The separate `Wake Workers` button was removed.
- 2026-05-22: Added `docs/learning/HERMES_GUILD_RUNTIME_CRASH_COURSE.md` to teach the project architecture, JSON/artifact reasoning, adapters, blackboard semantics, worker flow, and current file map in Vietnamese.
- 2026-05-22: Dashboard API health now includes `version`, `workspace`, and `db_path`; `open-guild-dashboard.ps1` rejects stale servers on the same port if their DB path does not match. Smoke passed on port `8780` and `/api/quest/manual` created `quest-one-button-smoke`.
- 2026-05-22: Expanded `docs/learning/HERMES_GUILD_RUNTIME_CRASH_COURSE.md` with code-level teaching sections: `guild-dashboard.html`, `guild-dashboard-server.py`, `run-guild-worker-agent.ps1`, adapter runtime, OpenCode adapter, smoke-test ladder, standard debugging loop, libraries/tools used, and a 7-day self-study plan.
- 2026-05-22: Added `docs/learning/HANDOFF_UI_GUILD_DEMO_2026-05-22.md` with current percent, files, endpoints, smoke status, known issues, and exact commands for continuing in a fresh context window.
- 2026-05-22: Real one-button UI wake smoke passed on port `8781` with `local-dry-run` visible worker terminals. Quest `quest-real-one-button-ui-wake-8781` moved `build`, `test`, and `review` through `done`; dashboard API poll showed review go from `claimed` to `done`.
- 2026-05-22: Added `scripts/guild.ps1` and installed a PowerShell profile function `guild` that opens the Guild Dashboard on port `8781` by default.
- 2026-05-22: Added a worker prompt context envelope: normal workers use `visible_scope=task_only` and should not inspect unrelated board/company context; `join_review` uses `visible_scope=join_review` and may report integration mismatches or propose bounded fix tasks.
- 2026-05-22: Parallel-first manual router smoke passed on fresh dashboard server port `8783`. Quest `quest-parallel-router-smoke-20260522-1515` created `spec -> build-1/build-2/build-3 -> review`; the three build tasks were claimable together, all three were claimed before review, reviewer had `no_claimable_task` while builds were claimed, and review unlocked only after all three builds were marked `done`.
- 2026-05-22: Added durable `needs_info` blocking semantics. Worker artifacts with `blocked_reason=needs_info` now set the task to `blocked` with persistent reason instead of `failed`, and `unlock-ready` does not reopen that task just because dependencies are satisfied. Smoke passed on `quest-needs-info-smoke-20260522-1535` with artifact `artifact-e88c7606`.
- 2026-05-22: Current UI demo routing contract is explicitly `manual-router v0`: this week uses fixed prompt/rules to split DAGs; next week Hermes planner can replace that fixed split with autonomous DAG planning after local-dry-run is smooth.
- 2026-05-22: Final local UI demo smoke passed on port `8785`. Quest `quest-final-ui-demo-local-20260522` launched three builder terminals plus one reviewer terminal; all five tasks reached `done`, with four artifacts (`implementation_result_1/2/3` and `integration_report`). Dashboard UI was opened at `http://127.0.0.1:8785/docs/incubation/guild-dashboard.html`.
- 2026-05-22: Dashboard UI now shows provider/router mode in the Hermes Routing Log and displays per-task artifact evidence chips. `local-dry-run` artifacts now include deterministic `commands_run` entries so the demo is honest about being a local adapter smoke, not real file work.
- 2026-05-22: Provider smoke was started but not completed. `opencode` direct adapter can run a tiny smoke, but worker-sized prompts exposed Windows/opencode wrapper issues and invalid provider output; `openrouter` direct adapter was added but current process lacked `OPENROUTER_API_KEY`. `opencode.json` was changed to use `{env:NINE_ROUTER_API_KEY}` instead of a literal local key. User plans to shut down and retry later with local env/key setup; do not expose or commit provider keys.
- 2026-05-24: Real provider UI demo work continued with OpenRouter, not Gemini. Gemini was added/kept as an adapter option but was unreliable in the actual smoke (`provider_failed` through the CLI path), so the real three-worker demo used `opencode`/`openrouter`/`groq`: worker-a through OpenCode, worker-b through OpenRouter, and worker-c through Groq. `_runtime/provider-secrets.local.ps1` was used as the ignored local key loader and must not be committed.
- 2026-05-25: Added Provider Lab to the Guild Dashboard. It reads `config/guild` provider transport/cartridge/capability config, saves whitelisted keys to ignored `_runtime/provider-secrets.local.ps1`, can list static/live models, and runs `Test Now` through `auto-ammo`.
- 2026-05-26: Corrected Guild progress framing: infrastructure exists, but the intended module-worker-artifact-meeting-fix-final loop is not complete. Added first bridge toward that model: skill-bound modules (`requirements`, `risk-analysis`, `verification`), `general` no longer wildcard-claims every task, OpenCode long prompts attach through files, dashboard server logs to `_runtime/dashboard/`, and `/api/hermes/finalize` can create module-specific fix tasks when builds fail or expected files are missing. See `_obsidian_vault/Daily/2026-05-26.md` / `[[Daily/2026-05-26]]`.
- 2026-05-26: Reduced Guild UI runtime hard-coding with `config/guild/guild-runtime.json`. Scheduler now chooses worker profiles from configured rank/skill capability instead of fixed `worker-a/b/c`, auto-rank maps configured workers to `opencode/openrouter/groq`, meeting/finalize creates only missing/failed module fix tasks, UI shows derived Guild Event Log plus Meeting Rounds, final assembly writes and validates `review.md`, `final-summary.md`, and `final-artifact.json`, and clean provider smoke passed outside sandbox for `opencode`, `openrouter`, and `groq`.

## Next Small Actions

1. Run one full visible dashboard smoke with real worker terminals using the config scheduler, not only API/direct smokes.
2. Decide whether Hermes finalization should stay API-owned or become a normal `join_review` worker claim path.
3. Expand scheduler policy if needed: weighted skill match, owner-worker pinning, provider quota checks, and retry ownership.
4. Keep using ignored `_runtime/provider-secrets.local.ps1` for provider keys; do not expose or commit key values.
5. Fix legacy cron job workdirs that still point to `D:\TuanKeCuoi`, if those jobs should remain active.

## Deferred

- n8n Daily Team workflows.
- Production Guild Dashboard UI/API.
- External memory providers.
- Vector database/RAG beyond current Obsidian FTS.
- Full integration between Hermes blackboard and Flock blackboard.

