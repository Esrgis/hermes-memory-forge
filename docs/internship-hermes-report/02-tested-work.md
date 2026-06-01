# Những Thứ Đã Test / Đã Làm

## 1. Memory Và Recall

Đã làm:

- Thiết kế 3 tầng memory:
  - hot memory
  - vault living files
  - daily notes
- Dùng Obsidian vault làm long-term semantic memory.
- Tạo/áp dụng Obsidian FTS search route.
- Tạo Memory Query Protocol để weak model biết search theo query packet.
- Ghi rule không lưu raw chat logs vào Obsidian.

Đã test:

- Search daily/shared memory bằng `scripts/search-obsidian-memory.ps1`.
- Đọc daily note theo ngày để reconstruct context.
- Dùng Current State / Assistant Shared Memory làm fast bootstrap.

## 2. Bounded Workspace Search

Đã làm:

- Chuẩn hóa file discovery:
  - `scripts/search-files.ps1`
  - `scripts/search-content.ps1`
  - `scripts/preview-file.ps1`
  - `scripts/inspect-workspace.ps1`
- Dùng Everything ES, fd, rg, bat, eza khi có.

Đã test:

- Workspace inspection.
- Bounded filename search.
- Bounded content search.
- Fallback khi Everything IPC/sandbox không hoạt động.

Giá trị:

- Giảm token, tránh recursive crawling.
- Giúp agent mới đọc repo nhanh hơn.

## 3. Blackboard SQLite Cơ Bản

Đã làm:

- `scripts/blackboard.py` với các bảng:
  - tasks
  - events
  - decisions
  - memory_candidates
  - workflow_runs
  - checkins
  - current_state
  - agent_status

Đã test:

- Init DB.
- Add events/tasks/checkins.
- Summary/list commands.

Lưu ý:

- SQLite runtime bền hơn khi đặt dưới AppData.
- Workspace `_runtime` từng gặp lỗi SQLite I/O.

## 4. Flock / Worker Team Prototype

Đã làm:

- Prototype dưới `_runtime/flock/worker_team_prototype.py`.
- Dùng Pydantic models:
  - GuildTask
  - ImplementationResult
  - TestResult
  - ReviewResult
  - TaskDecision
- Dùng SQLite durable queue:
  - guild_tasks
  - guild_artifacts

Đã test:

- In-memory Flock deterministic workers.
- AppData SQLite durable path.
- CLI create/list/inspect task.
- DAG unlock.
- Rank claim.
- Lease/heartbeat.
- Release expired task.
- Publish/list artifacts.
- Run join review.
- Generate bounded fix task.
- Dashboard JSON/text.

Kết luận:

- Blackboard/task/artifact model chạy được.
- Flock không nên là toàn bộ app, chỉ là candidate cho orchestration primitive.

## 5. Guild Dashboard

Đã làm:

- Static HTML dashboard.
- Four-column Blackboard layout.
- Dashboard API server.
- One-button `Giao Task Cho Hermes`.
- Provider Lab.
- Event Log và Meeting Rounds panel.

Đã test:

- Load dashboard JSON.
- Reset/seed/tick demo chain.
- API health.
- Manual quest API.
- Wake API dry-run.
- Visible worker terminal smoke.
- Final local UI demo với local-dry-run.

Giá trị:

- Người dùng nhìn được task state/artifacts thay vì agent làm ngầm.

## 6. Worker Loop Và Agent Profiles

Đã làm:

- Worker Bootstrap v0.
- Agent profiles:
  - hermes-codex
  - builder
  - worker-a
  - worker-b
  - worker-c
  - tester
  - reviewer
- Worker claim loop:
  - claim task
  - build prompt packet
  - call provider adapter
  - validate output
  - publish artifact
  - mark status
  - unlock dependencies

Đã test:

- local-dry-run worker.
- opencode worker smoke.
- visible worker terminal.
- reviewer claim path.
- invalid-output smoke.
- needs_info blocked semantics.

## 7. Provider Adapter Experiments

Đã làm:

- Provider adapter config:
  - capability-adapters
  - model-cartridges
  - provider-transports
  - provider-adapters
- Implemented adapters:
  - local-dry-run
  - local-file-writer
  - invalid-output-smoke
  - opencode
  - openrouter
  - gemini
  - groq
  - auto-ammo

Đã test:

- local-dry-run successful artifact.
- invalid-output blocked.
- opencode direct small JSON smoke.
- openrouter/groq provider smoke outside sandbox.
- Gemini kept as option but unreliable in actual smoke.
- Provider Lab deterministic smoke.

Lưu ý:

- Provider health phụ thuộc auth/network/environment.
- Không commit keys.

## 8. File Scope / Allowed Files

Đã làm:

- Worker artifact validation yêu cầu fields:
  - ok
  - summary
  - files_changed
  - commands_run
  - test_result
  - known_risks
  - blocked_reason
- Enforce `files_changed` nằm trong `allowed_files`.
- `local-file-writer` để test file output thật.

Đã test:

- First file-writer smoke fail vì allowed_files list/string mismatch.
- Fix normalization.
- Second smoke pass và tạo:
  - build-1.md
  - build-2.md
  - build-3.md
  - review.md

Kết luận:

- Đây là một gap thật được đóng: worker không chỉ publish fake artifact mà có thể tạo scoped files.

## 9. n8n Research Và Local Runtime

Đã làm:

- Clone n8n source dạng sparse vào `_runtime/research/n8n-sparse`.
- Đọc layout:
  - `packages/cli`
  - `packages/workflow`
  - `packages/core`
  - `packages/nodes-base/nodes`
- Xem các node liên quan:
  - Schedule
  - Telegram
  - TelegramTrigger
  - Webhook
  - ExecuteCommand
  - Code
  - If
  - Wait

Đã cài:

- n8n local package vào `_runtime/n8n-runner`.
- n8n version `2.21.7`.
- n8n user data dưới AppData:
  - `%LOCALAPPDATA%/hermes/n8n-home`

Đã test:

- n8n CLI version.
- n8n migrations under AppData.
- Import workflow.
- Start n8n server.
- Health/readiness 200.
- UI accessible ở `http://localhost:5678`.

Lưu ý:

- n8n DB dưới workspace `_runtime` bị SQLite readonly/I/O.
- Chạy n8n execute khi server đang chạy bị conflict Task Broker port `5679`.

## 10. Content Factory MVP

Đã làm:

- `scripts/content_factory.py`.
- SQLite queue dưới AppData:
  - content_jobs
  - content_artifacts
  - approval_events
- Runtime artifact files:
  - `_runtime/content-factory/runs/<job_id>/`
- Commands:
  - init
  - create-job
  - generate-script
  - render-placeholder
  - approval-message
  - send-approval
  - mark-decision
  - show-job
  - list-jobs
  - next-job
- Docs:
  - `docs/content-factory/MVP.md`
- n8n workflows:
  - dry-run candidate
  - real Telegram candidate
  - approval handler skeleton

Đã test:

- Create job.
- Generate idea/script/caption.
- Render placeholder file.
- Telegram dry-run.
- Mark approved.
- Show job/artifacts/approval events.
- Gửi Telegram thật thành công với message id `74`.
- Import 3 workflows vào n8n local DB.

Kết luận:

- MVP content factory skeleton đã chạy local.
- Chưa có TTS thật, render video thật, trend discovery thật, auto-post.

