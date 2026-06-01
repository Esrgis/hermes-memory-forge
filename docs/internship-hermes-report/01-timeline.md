# Timeline

## Trước 2026-05-18

- Định hướng ban đầu: xây một assistant local-first quanh Hermes, Obsidian, CLI workflow, Telegram, và runtime state.
- Ý tưởng lớn: biến Hermes thành personal cognitive OS, không chỉ chatbot.
- Obsidian được xác định là long-term semantic memory, không dùng làm runtime queue.

## 2026-05-18

Các việc chính:

- Thiết lập shared memory giữa Codex/Hermes qua Obsidian vault.
- Tạo/kiểm tra blackboard SQLite cơ bản cho tasks, events, decisions, checkins, current_state, agent_status.
- Thiết lập daily brief / Telegram route.
- Xác định Hermes gateway, cron, healthcheck là operator/runtime layer.
- Ghi rõ rule: không lưu raw chat logs vào Obsidian, chỉ lưu distilled memory.

Ý nghĩa cho báo cáo:

- Đây là ngày đặt nền tảng memory architecture.
- Học được bài học phân tách memory dài hạn và runtime state.

## 2026-05-19

Các việc chính:

- Bổ sung Obsidian FTS/RAG recall protocol.
- Tạo quy trình memory lookup để weak model không phải "nhớ bằng não".
- Đưa rule bounded retrieval vào bootstrap docs/scripts.
- Nghiên cứu Flock như candidate cho Worker Team runtime.
- Phân tách vai trò:
  - Guild App / Dashboard = app tổng
  - n8n = Daily Team runtime
  - Flock = Worker Team runtime candidate
  - Hermes = S-rank cognition / manager
  - Obsidian = archive library

Sự cố/bài học:

- Workspace rename/junction từng gây nguy hiểm cho filesystem.
- Rút ra rule dangerous-operation guard: trước khi delete/move/rename path phải inspect LinkType/Target/Attributes.

## 2026-05-20

Các việc chính:

- Tạo `_runtime/flock/worker_team_prototype.py`.
- Test Flock deterministic custom engines.
- Xây task/artifact contract đầu tiên:
  - GuildTask
  - ImplementationResult
  - TestResult
  - ReviewResult
  - TaskDecision
- Thêm SQLite durable queue:
  - `guild_tasks`
  - `guild_artifacts`
- Thêm CLI:
  - create/list/inspect task
  - unlock-ready
  - claim-next
  - heartbeat
  - release-expired
  - publish/list artifact
  - run-join-review
  - dashboard
- Test DAG unlock, rank claim, lease release, join review, generated fix task.

Sự cố/bài học:

- SQLite dưới workspace `_runtime` bị `sqlite3.OperationalError: disk I/O error`.
- Chuyển durable SQLite sang AppData cho ổn định.

## 2026-05-21

Các việc chính:

- Dashboard được refactor thành Blackboard 4 cột:
  - Ready
  - Claimed
  - Blocked
  - Done
- Thêm fake worker loop:
  - claim task
  - publish artifact
  - mark done
  - unlock dependencies
  - run join_review
- Thêm seed/reset/tick/dashboard scripts.
- Tạo Worker Bootstrap v0.
- Tạo agent profiles:
  - Hermes
  - Builder
  - Tester
  - Reviewer
- Tạo provider adapter shape:
  - local-dry-run
  - opencode
  - OpenRouter
  - Gemini
  - Cerebras
- Test Hermes -> opencode worker flow.

Ý nghĩa:

- Chứng minh blackboard + worker loop có thể chạy bằng deterministic worker trước khi gọi model thật.

## 2026-05-22

Các việc chính:

- Tách provider adapter logic thành Python runtime modules.
- Thêm configure command cho worker/provider/model.
- Thêm output validation cho worker artifacts.
- Thêm invalid-output smoke để chứng minh malformed model output bị chặn.
- Thêm dashboard API server:
  - `/api/health`
  - `/api/dashboard`
  - `/api/quest/manual`
  - `/api/wake`
- Dashboard UI có panel giao task, assign/wake worker.
- Một nút chính: `Giao Task Cho Hermes`.
- Thêm Vietnamese crash-course doc và handoff doc.
- Test one-button UI wake với local-dry-run visible worker terminals.
- Thêm `needs_info` blocked semantics.
- Test parallel-first manual router: spec -> 3 build tasks -> review.

Ý nghĩa:

- Đây là giai đoạn biến CLI prototype thành UI demo có thể quan sát.
- Bắt đầu có human-facing workflow thay vì chỉ command-line smoke.

## 2026-05-24

Các việc chính:

- Real provider UI demo tiếp tục với OpenRouter/Groq/OpenCode.
- Gemini được giữ làm option nhưng không ổn định trong smoke.
- Dùng ignored local provider secret loader, không commit key.

Ý nghĩa:

- Provider thật có thể chạy, nhưng reliability phụ thuộc environment/auth/network.

## 2026-05-25

Các việc chính:

- Thêm Provider Lab vào Guild Dashboard.
- Provider Lab đọc config trong `config/guild`.
- Có thể save whitelisted local keys vào ignored runtime secret file.
- Có thể list static/live models.
- Có thể test provider qua `auto-ammo`.

Ý nghĩa:

- Bắt đầu chuyển provider selection từ thủ công sang UI/config-driven.

## 2026-05-26

Các việc chính:

- Correct framing: Guild chưa "80% done"; chỉ là bridge/prototype.
- Skill binding:
  - requirements
  - risk-analysis
  - verification
- `general` không còn wildcard claim mọi task.
- OpenCode long prompt chuyển sang file attachment để tránh Windows command-line length error.
- Dashboard server ghi log rõ dưới `_runtime/dashboard`.
- `/api/hermes/finalize` tạo fix task khi build fail/missing output.
- Thêm `config/guild/guild-runtime.json` để giảm hard-code.
- Scheduler chọn worker từ rank/skill capability config.
- Meeting/finalize tạo fix task chỉ cho module thiếu/fail.
- UI thêm derived Guild Event Log và Meeting Rounds.
- Final assembly tạo/validate:
  - `review.md`
  - `final-summary.md`
  - `final-artifact.json`
- Thêm deterministic `local-file-writer` adapter.
- Smoke `quest-file-writer-smoke-v2-20260526` pass: worker tạo scoped files thật.

Quyết định:

- Giữ `/api/hermes/finalize` là bridge v1.
- Chưa chuyển finalization thành normal worker-claimed `final_review`.
- Chưa thêm durable event table.
- Chưa mở rộng scheduler policy.

## 2026-05-27

Các việc chính:

- Đọc lại ngày 26/05 và chốt việc hôm nay.
- Phân tích content factory MVP cho TikTok/Shorts.
- Quyết định không bê nguyên Guild runtime vào content factory.
- Kiến trúc content factory MVP:
  - n8n = scheduler/orchestrator/Telegram approval
  - Hermes/local script = reasoning/content generation
  - SQLite = runtime queue/state
  - Obsidian = long-term memory/style notes
- Clone n8n source dạng sparse để nghiên cứu.
- Cài n8n local vào `_runtime/n8n-runner`.
- n8n user folder/DB đặt dưới AppData vì SQLite trong workspace có vấn đề.
- Start n8n server:
  - UI: `http://localhost:5678`
  - health/readiness OK
- Tạo content factory CLI:
  - `scripts/content_factory.py`
- Tạo content factory docs/workflows:
  - `docs/content-factory/MVP.md`
  - n8n workflow JSON dry-run
  - n8n workflow JSON real Telegram
  - n8n approval handler skeleton
- Smoke local content factory:
  - create job
  - generate idea/script/caption
  - render placeholder
  - send Telegram dry-run
  - mark approved
- Gửi Telegram thật thành công cho job approval, message id `74`.
- Import 3 workflow vào n8n local DB:
  - Content Factory - Candidate Dry Run
  - Content Factory - Candidate Real Telegram
  - Content Factory - Telegram Approval Handler Skeleton

