# Guild Debug Navigation Map

Mục tiêu của file này: khi debug Guild, con người và Codex nhìn cùng một bản đồ. Mỗi mục dưới đây là một vai trò trong runtime; Ctrl+Click vào link để nhảy thẳng tới file cần đọc.

Không dùng file này như tài liệu kiến trúc dài. Dùng nó như bảng điều hướng khi có bug: xác định bug thuộc vai nào, mở đúng file, xem đúng evidence.

## 0. Luồng Chạy Tổng Quát

```text
UI
-> Dashboard API
-> Planner / router
-> Blackboard task DB
-> Worker agent
-> Provider adapter
-> Artifact validation
-> Artifact / file output
-> Finalizer / join review
-> Dashboard evidence
```

Nếu debug bị rối, quay lại luồng này và hỏi: "bug đang vỡ ở đoạn nào?"

## 0.1. Layer Input / Output Contract

Dùng bảng này để vẽ biểu đồ hoặc debug theo tầng. Mỗi layer phải nói rõ nó nhận gì, sinh gì, và log event nào.

| Layer | Input | Output | Main events |
| --- | --- | --- | --- |
| UI console | user prompt, adapter choice, quest id | `POST /api/hermes/plan-preview`, `POST /api/hermes/quest`, `POST /api/wake` | frontend log only |
| Dashboard API | HTTP body, planner config, runtime config | quest workspace, task chain, wake calls, dashboard JSON | `quest_hermes_created`, `wake_start`, `wake_profile` |
| Planner/router | prompt, allowed files, planner skill pack | `GuildTask` specs with skill/rank/dependencies | plan preview events |
| Blackboard | task records, status updates, artifacts | claimable tasks, dashboard read model | CLI result JSON |
| Worker agent | claimed task, profile, adapter route | provider prompt packet, artifact payload, task status | `worker_task_claimed`, `worker_task_done`, `worker_task_blocked`, `worker_task_failed` |
| Provider adapter | prompt packet, model/provider config | raw provider text normalized into artifact JSON | adapter result JSON |
| Validation/grounding | adapter result, allowed files, task contract | valid artifact or blocked reason | `invalid_adapter_output`, `ungrounded_artifact_output`, `files_outside_allowed_scope` |
| File writer | `file_outputs[]`, workspace path | files under `guild-workspaces/<quest-id>/` | `file_output_write` in payload |
| Finalizer/review | done build artifacts, review task | `review.md`, `final-summary.md`, `final-artifact.json` | `finalize_review_terminal`, finalizer events |

Event schema v1 for runtime logs:

```json
{
  "event": "worker_task_claimed",
  "details": {
    "schema_version": "guild_event_v1",
    "layer": "worker-agent",
    "phase": "claim",
    "severity": "info",
    "quest_chain_id": "quest-...",
    "task_id": "task-...",
    "profile": "worker-a",
    "adapter": "auto-ammo",
    "input": { "source": "blackboard.claim-next" },
    "output": { "claimed": true }
  }
}
```

Debug rule: if a bug cannot be assigned to one layer and one input/output edge, the log is not good enough yet.

## 1. UI / Giao Diện

Vai trò:

- Hiển thị board Ready / Claimed / Blocked / Done.
- Nhận prompt từ người dùng.
- Gọi API tạo quest và wake worker.
- Hiển thị routing log, provider lab, artifact evidence.

Mở file:

- [Dashboard HTML](../incubation/guild-dashboard.html)
- [System Map Guild Demo](SYSTEM_MAP_GUILD_DEMO.md)
- [UI demo handoff](HANDOFF_UI_GUILD_DEMO_2026-05-22.md)

Khi nghi UI bug:

- Nếu button không chạy, kiểm tra request gọi API nào trong [guild-dashboard.html](../incubation/guild-dashboard.html).
- Nếu board nhìn sai, đừng kết luận từ UI trước; kiểm tra `/api/dashboard` hoặc dashboard JSON.
- Không tự mở UI/server khi đang debug headless, trừ khi người dùng yêu cầu.

## 2. Dashboard API / Local Server

Vai trò:

- Nhận request từ UI.
- Tạo quest workspace.
- Tạo task chain.
- Gọi wake route để mở worker.
- Trả dashboard JSON cho UI.

Mở file:

- [scripts/guild-dashboard-server.py](../../scripts/guild-dashboard-server.py)
- [scripts/open-guild-dashboard.ps1](../../scripts/open-guild-dashboard.ps1)
- [scripts/export-guild-dashboard.ps1](../../scripts/export-guild-dashboard.ps1)

Route thường phải kiểm:

- `GET /api/health`
- `GET /api/dashboard`
- `POST /api/quest/manual`
- `POST /api/hermes/quest`
- `POST /api/wake`
- `POST /api/hermes/finalize`
- `POST /api/task/retry-blocked`

Khi nghi API bug:

- Quest không sinh task: mở [guild-dashboard-server.py](../../scripts/guild-dashboard-server.py), tìm route tạo quest.
- Wake không mở worker: kiểm `POST /api/wake` và file [start-guild-worker-terminal.ps1](../../scripts/start-guild-worker-terminal.ps1).
- Finalizer spam hoặc sai: kiểm route `/api/hermes/finalize`, rồi kiểm artifact/file thật trong `guild-workspaces/<quest-id>/`.

## 3. Planner / Router / Task Shape

Vai trò:

- Chuyển prompt thành task chain.
- Chọn template và skill.
- Quyết định task nào chạy song song, task nào chờ review.
- Gắn allowed files, expected outputs, required skill/rank.

Mở file:

- [config/guild/planner-skills.json](../../config/guild/planner-skills.json)
- [config/guild/guild-runtime.json](../../config/guild/guild-runtime.json)
- [skills/guild-planner/SKILL.md](../../skills/guild-planner/SKILL.md)

Khi nghi planner bug:

- Nếu prompt "3 phần song song" nhưng chỉ sinh 1 task build, kiểm `planner-skills.json`.
- Nếu worker không claim task, kiểm `required_skill`, `required_rank`, và worker capability trong config.
- Nếu provider được nhắc file/route giả, thêm grounding vào planner/task packet thay vì để model đoán.

## 4. Blackboard / Task DB

Vai trò:

- Lưu task.
- Lưu artifact.
- Claim task theo rank/skill.
- Unlock dependency.
- Export dashboard state.

Mở file:

- [scripts/guild-worker-team.py](../../scripts/guild-worker-team.py)
- [_runtime/flock/worker_team_prototype.py](../../_runtime/flock/worker_team_prototype.py)

SQLite runtime:

- `C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite`

Command định hướng:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py --help
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py inspect-task TASK_ID
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id QUEST_ID --include-tasks --include-artifacts
```

Khi nghi blackboard bug:

- Task không mở: kiểm dependency và plan gate.
- Task không claim: kiểm status, rank, skill, lease, cooldown.
- Artifact có nhưng UI không thấy: kiểm dashboard export/API mapping.

## 5. Worker Agent / Claim -> Adapter -> Artifact

Vai trò:

- Claim task đang `open`.
- Tạo prompt packet có scope rõ.
- Gọi provider adapter.
- Validate output.
- Publish artifact.
- Set task `done`, `blocked`, hoặc `failed`.
- Unlock task phụ thuộc.

Mở file:

- [scripts/run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1)
- [scripts/start-guild-worker-terminal.ps1](../../scripts/start-guild-worker-terminal.ps1)
- [scripts/configure-guild-worker.ps1](../../scripts/configure-guild-worker.ps1)

Khi nghi worker bug:

- Worker chạy quá nhanh: có thể là `local-dry-run` hoặc `local-file-writer`, không phải provider thật.
- Worker báo done nhưng file thiếu: kiểm `files_changed`, `file_outputs`, và grounding trên disk.
- Worker failed vì output sai schema: mở validation path trong [run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1) và [validation.py](../../scripts/guild_provider_adapters/validation.py).

## 6. Provider Adapter Layer

Vai trò:

- Nối worker với local smoke hoặc provider thật.
- Chuẩn hóa response thành artifact JSON.
- Chặn provider trả output sai schema.
- Ghi payload/evidence để debug thật giả.

Mở folder:

- [scripts/guild_provider_adapters](../../scripts/guild_provider_adapters)

Mở file lõi:

- [base.py](../../scripts/guild_provider_adapters/base.py)
- [registry.py](../../scripts/guild_provider_adapters/registry.py)
- [invoke.py](../../scripts/guild_provider_adapters/invoke.py)
- [validation.py](../../scripts/guild_provider_adapters/validation.py)
- [ladder.py](../../scripts/guild_provider_adapters/ladder.py)
- [capabilities.py](../../scripts/guild_provider_adapters/capabilities.py)

Adapter deterministic:

- [local_dry_run.py](../../scripts/guild_provider_adapters/local_dry_run.py)
- [local_file_writer.py](../../scripts/guild_provider_adapters/local_file_writer.py)
- [invalid_output.py](../../scripts/guild_provider_adapters/invalid_output.py)
- [provider_exhausted_smoke.py](../../scripts/guild_provider_adapters/provider_exhausted_smoke.py)

Adapter provider thật:

- [opencode.py](../../scripts/guild_provider_adapters/opencode.py)
- [openrouter.py](../../scripts/guild_provider_adapters/openrouter.py)
- [openai_compatible.py](../../scripts/guild_provider_adapters/openai_compatible.py)
- [gemini.py](../../scripts/guild_provider_adapters/gemini.py)
- [groq.py](../../scripts/guild_provider_adapters/groq.py)

PowerShell wrapper:

- [scripts/invoke-guild-provider-adapter.ps1](../../scripts/invoke-guild-provider-adapter.ps1)
- [scripts/get-guild-provider-adapter.ps1](../../scripts/get-guild-provider-adapter.ps1)

Khi nghi adapter bug:

- Kiểm adapter name có được bind trong [registry.py](../../scripts/guild_provider_adapters/registry.py).
- Kiểm provider route có đi qua [invoke.py](../../scripts/guild_provider_adapters/invoke.py) hay PowerShell wrapper.
- Kiểm payload JSON trong `_runtime/guild-worker-agent/` trước khi tin dashboard.

## 7. Provider Config / Capability Pool

Vai trò:

- Lưu transport/provider.
- Lưu model cartridge.
- Lưu capability adapter.
- Chọn ammo ladder cho build/review.
- Giữ 9Router là path explicit nếu không được yêu cầu làm default.

Mở file:

- [config/guild/provider-transports.json](../../config/guild/provider-transports.json)
- [config/guild/model-cartridges.json](../../config/guild/model-cartridges.json)
- [config/guild/capability-adapters.json](../../config/guild/capability-adapters.json)
- [config/guild/provider-adapters.json](../../config/guild/provider-adapters.json)

Khi nghi provider config bug:

- Provider list đúng nhưng chat fail: kiểm adapter payload và lỗi auth/provider.
- Auto-rank chọn sai provider: kiểm capability mapping, không đoán từ UI.
- Không đọc hoặc commit secret; keys nằm ở ignored local runtime file.

## 8. Artifact Schema / Validation

Vai trò:

- Ép provider trả object đủ field để runtime quyết định.
- Chặn văn xuôi hoặc JSON thiếu field.
- Gắn validation result vào artifact.
- Kiểm file outputs khi adapter ghi file.

Mở file:

- [scripts/guild_provider_adapters/validation.py](../../scripts/guild_provider_adapters/validation.py)
- [scripts/run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1)
- [GUILD_ARTIFACT_SCHEMA_LESSON_2026-06-05.md](GUILD_ARTIFACT_SCHEMA_LESSON_2026-06-05.md)
- [GUILD_REAL_PROVIDER_ARTIFACT_ROUTE_LESSON_2026-06-05.md](GUILD_REAL_PROVIDER_ARTIFACT_ROUTE_LESSON_2026-06-05.md)

Field tối thiểu thường gặp:

```text
ok
summary
files_changed
commands_run
test_result
known_risks
blocked_reason
```

Khi nghi artifact bug:

- Nếu `invalid_adapter_output`, không sửa UI trước; sửa schema/validation hoặc prompt packet.
- Nếu `ok=true` nhưng `files_changed` không tồn tại trên disk, bug nằm ở grounding/file writer path.
- Nếu reviewer bị chặn, kiểm `join_review` validation rule riêng.

## 9. Finalizer / Review / Meeting

Vai trò:

- Đọc upstream artifacts.
- Tạo `review.md`, `final-summary.md`, `final-artifact.json`.
- Chỉ tạo fix task khi evidence thiếu hoặc build failed.
- Không xem dashboard done là bằng chứng cuối.

Mở file:

- [scripts/guild-dashboard-server.py](../../scripts/guild-dashboard-server.py)
- [scripts/run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1)
- [_runtime/flock/worker_team_prototype.py](../../_runtime/flock/worker_team_prototype.py)

Mở runtime output:

- `guild-workspaces/<quest-id>/review.md`
- `guild-workspaces/<quest-id>/final-summary.md`
- `guild-workspaces/<quest-id>/final-artifact.json`

Khi nghi finalizer bug:

- Kiểm file thật trong `guild-workspaces/<quest-id>/`.
- Kiểm artifact upstream của từng build task.
- Kiểm event log xem finalize bị gọi lặp hay bị blocked.

## 10. Evidence / Runtime Truth

Vai trò:

- Chứng minh run là preview-only, local smoke, hay provider thật.
- Chứng minh provider có gọi thật hay chỉ retry noise.
- Chứng minh file output có tồn tại thật.

Mở runtime path:

- `_runtime/dashboard/guild-events.jsonl`
- `_runtime/dashboard/guild-dashboard.json`
- `_runtime/guild-worker-agent/`
- `_runtime/guild-worker-agent/terminal-sessions/`
- `guild-workspaces/<quest-id>/`

Evidence ladder:

1. `_runtime/dashboard/guild-events.jsonl`
2. `_runtime/guild-worker-agent/*payload.json`
3. `guild-workspaces/<quest-id>/`
4. dashboard JSON
5. process state, chỉ khi cần

Khi trả lời bug runtime:

- Nói rõ quest id.
- Nói rõ adapter.
- Nói rõ local smoke hay provider thật.
- Nói rõ worker có launch không.
- Nói rõ file expected có tồn tại không.

## 11. Smoke Tests / Regression Gates

Vai trò:

- Kiểm nhanh hợp đồng sau khi sửa.
- Ưu tiên deterministic smoke trước provider thật.
- Không đốt quota nếu local contract còn vỡ.

Mở file:

- [scripts/test-guild-local-file-writer-smoke.ps1](../../scripts/test-guild-local-file-writer-smoke.ps1)
- [scripts/test-guild-artifact-validation-smoke.py](../../scripts/test-guild-artifact-validation-smoke.py)
- [scripts/test-guild-worker-artifact-validation-smoke.ps1](../../scripts/test-guild-worker-artifact-validation-smoke.ps1)
- [scripts/test-guild-worker-contract-smoke.ps1](../../scripts/test-guild-worker-contract-smoke.ps1)
- [scripts/test-guild-claim-resume-smoke.py](../../scripts/test-guild-claim-resume-smoke.py)

Smoke order khuyến nghị:

```text
artifact validation
-> worker contract
-> claim/resume
-> local-file-writer
-> API route smoke
-> provider adapter smoke
-> visible UI demo only when explicitly needed
```

## 12. Bug Triage Theo Triệu Chứng

### UI không phản ứng

Mở:

- [guild-dashboard.html](../incubation/guild-dashboard.html)
- [guild-dashboard-server.py](../../scripts/guild-dashboard-server.py)

Kiểm:

- Browser request gọi route nào.
- API server có đang đúng workspace/db path không.
- `/api/health` và `/api/dashboard`.

### Quest tạo sai task

Mở:

- [planner-skills.json](../../config/guild/planner-skills.json)
- [guild-runtime.json](../../config/guild/guild-runtime.json)
- [guild-dashboard-server.py](../../scripts/guild-dashboard-server.py)

Kiểm:

- Template nào được chọn.
- Prompt có bị route sang `standard-build` thay vì `three-part-local-demo` không.
- Task có `required_skill` đúng không.

### Worker không claim

Mở:

- [guild-worker-team.py](../../scripts/guild-worker-team.py)
- [_runtime/flock/worker_team_prototype.py](../../_runtime/flock/worker_team_prototype.py)
- [run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1)

Kiểm:

- Task status có `open` không.
- Rank/skill có khớp không.
- Lease/cooldown có giữ task không.
- Worker có bị `no_claimable_task` không.

### Worker done nhưng file thiếu

Mở:

- [local_file_writer.py](../../scripts/guild_provider_adapters/local_file_writer.py)
- [run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1)
- [validation.py](../../scripts/guild_provider_adapters/validation.py)

Kiểm:

- `files_changed`.
- `file_outputs`.
- File thật trong `guild-workspaces/<quest-id>/`.
- `artifact_grounding_validation.valid`.

### Provider có vẻ đang đốt quota

Mở:

- `_runtime/guild-worker-agent/*payload.json`
- [invoke.py](../../scripts/guild_provider_adapters/invoke.py)
- [ladder.py](../../scripts/guild_provider_adapters/ladder.py)
- [capability-adapters.json](../../config/guild/capability-adapters.json)

Kiểm:

- `provider_usage`.
- `total_tokens`.
- Adapter selected.
- Retry count là provider call thật hay terminal failure noise.

### `invalid_adapter_output`

Mở:

- [validation.py](../../scripts/guild_provider_adapters/validation.py)
- [run-guild-worker-agent.ps1](../../scripts/run-guild-worker-agent.ps1)
- [invalid_output.py](../../scripts/guild_provider_adapters/invalid_output.py)

Kiểm:

- Missing field nào.
- JSON parse fail vì multiline/raw control chars không.
- Provider có trả văn xuôi thay vì JSON không.

### Finalizer spam hoặc review sai

Mở:

- [guild-dashboard-server.py](../../scripts/guild-dashboard-server.py)
- [_runtime/flock/worker_team_prototype.py](../../_runtime/flock/worker_team_prototype.py)
- `guild-workspaces/<quest-id>/`

Kiểm:

- Event log finalize.
- Upstream artifacts.
- Expected files.
- Fix tasks có bị tạo lặp không.

## 13. Quy Tắc Debug Chung

- Đừng tin board trước evidence.
- Đừng gọi provider thật khi local smoke đang vỡ.
- Đừng tự mở dashboard/UI khi user không yêu cầu.
- Đừng đọc secret file.
- Đừng sửa nhiều layer cùng lúc nếu chưa biết bug thuộc layer nào.
- Sau mỗi sửa meaningful, chạy smoke nhỏ nhất chứng minh đúng layer đó.
