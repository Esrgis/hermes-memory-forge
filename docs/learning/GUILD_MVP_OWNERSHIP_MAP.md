# Ban Do Ownership MVP Guild

Tai lieu nay la ban do nho de minh chiem lai quyen so huu luong MVP hien tai cua Hermes Guild.

No co tinh bo qua Provider Lab, n8n, Telegram, memory pipeline rong, provider that, va refactor lon.

## Luong MVP

```text
user giao task
-> dashboard/API tao quest
-> blackboard luu task
-> worker claim mot task
-> adapter tao ket qua
-> worker publish artifact va cap nhat status
-> dashboard/CLI doc status
```

Ban ngan gon:

```text
task -> blackboard -> worker -> result/status -> dashboard/CLI
```

## Can Own Cai Gi Truoc

Hay own luong nay truoc khi doi architecture:

1. Co mot task ton tai.
2. Task duoc luu vao SQLite.
3. Worker claim duoc task.
4. Worker tra ve artifact hop le.
5. Task chuyen thanh `done`, `blocked`, hoac `failed`.
6. Dashboard hoac CLI hien duoc ket qua.

Neu mot trong cac buoc tren chua ro, dung lai va doc dung layer do truoc khi them feature.

## Cac File Chinh

### Layer Dashboard/API

File:

- `scripts/guild-dashboard-server.py`

Nhiem vu:

- Nhan request tu UI/API.
- Tao quest workspace trong `guild-workspaces/`.
- Tao chuoi task thong qua blackboard CLI.
- Goi worker thong qua `/api/wake`.
- Export dashboard JSON.

Route quan trong:

- `POST /api/quest/manual`
- `POST /api/hermes/quest`
- `POST /api/wake`
- `GET /api/dashboard`

Luu y:

- Neu blackboard con kho hieu, dung hoc file nay dau tien.
- Hay xem dashboard/API nhu lop dieu phoi ben ngoai blackboard.

### Layer UI

File:

- `docs/incubation/guild-dashboard.html`

Nhiem vu:

- Hien bang task.
- Gui request giao task toi local dashboard API.
- Hien status, event, artifact, va provider settings.

Cach own:

- Xem UI nhu vo ngoai cua API.
- Neu UI gay roi, hay test cung luong do bang CLI/API truoc.

### Layer Blackboard CLI

Files:

- `scripts/guild-worker-team.py`
- `_runtime/flock/worker_team_prototype.py`

Nhiem vu:

- Luu task.
- Luu artifact.
- Claim task.
- Cap nhat status task.
- Export dashboard state.

Thuc te hien tai:

- `_runtime/flock/worker_team_prototype.py` nghe nhu prototype, nhung hien dang la runtime core.
- Dung refactor file nay cho den khi co mot smoke command deterministic chay on dinh.

Command quan trong:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py --help
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py inspect-task TASK_ID
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id QUEST_ID --include-tasks --include-artifacts
```

### Layer Worker

Files:

- `scripts/run-guild-worker-agent.ps1`
- `scripts/start-guild-worker-terminal.ps1`

Nhiem vu:

- Claim mot task dang `open`.
- Tao task packet cho worker.
- Goi adapter/provider.
- Validate artifact JSON tra ve.
- Publish artifact.
- Set status task.
- Unlock task phu thuoc.

File quan trong nhat de own:

- `scripts/run-guild-worker-agent.ps1`

Ly do:

- No la cay cau noi blackboard state voi ket qua worker.

### Layer Adapter

Folder:

- `scripts/guild_provider_adapters/`

Adapter quan trong:

- `local_dry_run.py`: smoke deterministic, khong ghi file.
- `local_file_writer.py`: smoke deterministic, ghi file trong scope duoc phep.
- provider adapters: de sau, khi local smoke on dinh.

Baseline MVP hien tai:

- Uu tien `local-file-writer` de chung minh worker co the ghi file va publish artifact ma khong can API key.

### Layer Config

Files:

- `config/guild/guild-runtime.json`
- `config/guild/agent-profiles.json`

Nhiem vu:

- Dinh nghia module tracks.
- Dinh nghia skill/rank cua worker.
- Dinh nghia review/final assembly expectation.

Quy tac ownership:

- Config phai giai thich duoc vi sao worker nao duoc claim task nao.
- Neu worker khong claim duoc task, kiem tra `required_rank` va `required_skill` o day.

## Runtime State Nam O Dau

SQLite task/artifact cua Guild:

```text
C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite
```

Bang quan trong:

```text
guild_tasks
guild_artifacts
```

Dashboard export/cache:

```text
_runtime/dashboard/guild-dashboard.json
```

Quest workspace:

```text
guild-workspaces/<quest_chain_id>/
```

Obsidian la memory dai han, khong phai runtime state song.

## Cach Debug Luong MVP

### 1. Task Da Duoc Tao Chua?

Check:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id QUEST_ID --include-tasks
```

Neu khong thay task:

- Xem `scripts/guild-dashboard-server.py`.
- Kiem tra cho goi `create-task`.

### 2. Task Co Claim Duoc Khong?

Check:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py inspect-task TASK_ID
```

Nhin cac field:

- `status`
- `required_rank`
- `required_skill`
- `depends_on`
- `plan_review_status`

Neu khong claim duoc:

- Worker co the thieu rank hoac skill.
- Dependency co the chua `done`.
- Plan review gate co the van dang chan.

### 3. Worker Co Tao Artifact Hop Le Khong?

Chay worker mot lan:

```powershell
.\scripts\run-guild-worker-agent.ps1 -Profile reviewer -Adapter local-file-writer -QuestChainId QUEST_ID -Once -Json
```

Nhin cac field:

- `ok`
- `artifact`
- `adapter_result`
- `adapter_output_validation`
- `file_scope_validation`

Neu invalid:

- Doc validation error truoc khi sua code.

### 4. Dashboard/CLI Co Thay Ket Qua Khong?

Check:

```powershell
_runtime\research\flock\.venv\Scripts\python.exe .\scripts\guild-worker-team.py dashboard --quest-chain-id QUEST_ID --include-tasks --include-artifacts
```

Expected:

- status task da doi
- artifact count tang
- artifact payload co worker output

## Chua Nen Dung Vao Luc Dau

Khi dang hoc luong MVP, tranh cac phan nay:

- n8n runtime
- Telegram reporting
- provider key handling
- Provider Lab polish
- Hermes autonomous planning
- refactor lon
- di chuyen `_runtime/flock/worker_team_prototype.py`

Chung co the quan trong sau nay, nhung khong can de own MVP.

## Quy Tac Cho Moi Lan Sua Code

Truoc khi sua code, phai noi:

1. Muc tieu buoc nay.
2. File se sua.
3. Vi sao can sua.
4. Command test sau khi sua.

Sau khi sua code, phai noi:

1. Da thay doi gi.
2. Da chay command nao.
3. Pass hay fail.
4. Luong vua sua hoat dong nhu the nao.

Neu test fail, doc log/output truoc khi sua tiep.

## Buoc Nho Nhat Tiep Theo

Tao mot smoke command deterministic cho luong MVP:

```text
create quest
-> create/seed tasks
-> run local-file-writer worker
-> publish artifacts
-> show dashboard result
```

Command nay se la day an toan truoc khi cleanup hoac refactor.
