# System Map: Guild UI Demo (HermesGuildCore)

Mục tiêu của map này: cho người mới (hoặc quay lại sau vài ngày) nhìn 1 trang là biết “chạy ở đâu, dữ liệu nằm đâu, luồng chạy như nào”.

## 1) Luồng 1 nút (UI-first demo)

1. Người dùng nhập “Prompt for Hermes” trên dashboard UI
2. UI gọi `POST /api/quest/manual`
3. Server tạo quest + tasks (manual-router v0), rồi unlock các task `open`
4. UI gọi `POST /api/wake` để mở terminal worker (visible)
5. Worker tự claim task, gọi adapter, publish artifact, cập nhật status, unlock dependency
6. UI auto-refresh đọc `/api/dashboard` để cập nhật board Ready/Claimed/Blocked/Done

Ghi chú: “Hermes Routing Log” trên UI là log định tuyến/progress cho demo (không phải Hermes gateway thật, không phải chain-of-thought).

## 2) Các entrypoint quan trọng

- Dashboard UI: `docs/incubation/guild-dashboard.html`
- Dashboard API server: `scripts/guild-dashboard-server.py`
- Launcher dashboard (chống stale server/db_path mismatch): `scripts/open-guild-dashboard.ps1`
- Command mở nhanh: `scripts/guild.ps1` + PowerShell function `guild` (cài bởi `scripts/install-guild-command.ps1`)

## 3) Worker runtime (blackboard loop)

- Terminal launcher (mở cửa sổ worker): `scripts/start-guild-worker-terminal.ps1`
- Worker tick (claim -> adapter -> artifact -> status -> unlock): `scripts/run-guild-worker-agent.ps1`

Guardrail quan trọng:
- Worker prompt có `visible_scope=task_only` (mặc định) để không “biết cả công ty”.
- `join_review` dùng `visible_scope=join_review` để đọc/đối chiếu artifact upstream và đề xuất fix nhỏ.

Chuẩn hoá `needs_info`:
- Nếu `blocked_reason=needs_info` thì task được set `blocked` (không `failed`) và vẫn publish artifact để UI thấy lý do.

## 4) Provider adapters (deterministic trước, provider thật sau)

Python adapter runtime: `scripts/guild_provider_adapters/`

- `local_dry_run.py`: deterministic, không gọi model
  - Marker smoke: nếu prompt/message có `[needs_info]` thì adapter trả artifact `blocked_reason=needs_info`
- `opencode.py`: gọi OpenCode CLI (khi chuyển sang provider thật)
- `registry.py`, `base.py`, `invoke.py`: khung registry + dataclasses + entrypoint

## 5) Source of truth / state

- SQLite (task + artifact): `C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite`
- Export dashboard JSON: `_runtime/dashboard/guild-dashboard.json`

## 6) Lệnh chạy nhanh (demo)

Mở dashboard (port mới nếu port cũ bị stale):

```powershell
guild -Port 8781
```

Không mở browser + không export (tiện test command):

```powershell
guild -Port 8781 -NoOpen -NoExport
```

Smoke `needs_info`:
- Giao task trên UI, trong prompt thêm marker: `[needs_info]`
- Kỳ vọng: task chuyển `blocked` và artifact ghi `blocked_reason=needs_info`

## 7) Tài liệu định hướng (đọc theo thứ tự)

- Handoff demo UI: `docs/learning/HANDOFF_UI_GUILD_DEMO_2026-05-22.md`
- Crash course: `docs/learning/HERMES_GUILD_RUNTIME_CRASH_COURSE.md`
- Task ledger: `TASKS.md`
- Daily memory: `_obsidian_vault/Daily/2026-05-22.md`
