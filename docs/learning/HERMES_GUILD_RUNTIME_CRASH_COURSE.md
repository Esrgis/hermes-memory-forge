# Hermes Guild Runtime Crash Course

Mục tiêu của file này: giúp bạn hiểu dự án đủ để không bị cảm giác “Codex múa gì đó”. Đây không phải tài liệu API đầy đủ. Nó là bản đồ tư duy senior: vì sao hệ thống được chia như vậy, dữ liệu đi qua đâu, và những quyết định kỹ thuật nào là quan trọng.

## 1. Dự án này thật ra đang xây cái gì?

HermesGuildCore không phải chỉ là chatbot. Nó là một runtime local-first để biến yêu cầu của bạn thành task có trạng thái, có worker, có artifact, có evidence.

Mô hình hiện tại:

```text
Bạn nhập task ở Dashboard
-> Hermes route/split theo luật cố định
-> ghi tasks vào SQLite blackboard
-> worker terminals tự claim task
-> adapter gọi provider/AI CLI
-> worker publish artifact
-> dashboard đọc trạng thái từ blackboard
```

Các phần chính:

```text
Dashboard UI       = nơi bạn nhìn và giao task
Dashboard API      = server local nhận lệnh từ UI
SQLite blackboard  = task queue + artifact store
Worker agent       = claim task, gọi adapter, publish artifact
Adapter            = driver nối worker với provider/tool
Provider/AI CLI    = opencode/openrouter/gemini/local-dry-run
Obsidian           = memory dài hạn, không phải runtime state
```

## 2. Vì sao cần blackboard?

Nếu chỉ gọi model trực tiếp, model có thể nói “xong rồi” nhưng không có trạng thái thật. Blackboard ép mọi việc đi qua state rõ ràng:

```text
open -> claimed/running -> done/failed
blocked -> open khi dependency done
```

Blackboard hiện nằm trong SQLite:

```text
C:\Users\nthan\AppData\Local\hermes\flock\worker_team.sqlite
```

Hai bảng quan trọng:

```text
guild_tasks      = task queue
guild_artifacts  = kết quả worker publish
```

Code chính:

```text
_runtime/flock/worker_team_prototype.py
scripts/guild-worker-team.py
```

## 3. Vì sao output nên là JSON?

Đây là một trong những kinh nghiệm senior quan trọng nhất.

Text tự do phù hợp cho người đọc, nhưng rất tệ cho runtime. Runtime cần biết:

```text
task có thành công không?
file nào đổi?
đã chạy command gì?
test pass chưa?
có risk gì?
có bị blocked không?
```

Nếu model trả văn xuôi:

```text
Tôi nghĩ task này đã ổn, có thể dùng được.
```

thì runtime không biết nên mark `done`, `failed`, hay `blocked`.

Nếu model trả JSON:

```json
{
  "ok": true,
  "summary": "Implemented scoped dashboard change.",
  "files_changed": ["docs/incubation/guild-dashboard.html"],
  "commands_run": ["python -B scripts/guild_provider_adapters/invoke.py --help"],
  "test_result": "passed",
  "known_risks": [],
  "blocked_reason": null
}
```

thì runtime có thể validate và quyết định tự động.

Đó là lý do có validator trong:

```text
scripts/run-guild-worker-agent.ps1
```

Validator bắt buộc field:

```text
ok
summary
files_changed
commands_run
test_result
known_risks
blocked_reason
```

Nếu provider/model trả sai schema, task không được mark done. Nó bị chặn bằng:

```text
blocked_reason = invalid_adapter_output
```

Smoke đã chứng minh bằng adapter test-only:

```text
invalid-output-smoke
```

## 2026-05-26 update: config-driven Guild loop

Guild UI runtime đã chuyển bước đầu từ hard-code sang config:

```text
config/guild/guild-runtime.json
```

File này mô tả:

```text
module_tracks      = mỗi module cần skill nào và ghi file nào
scheduler          = chọn worker theo rank/skill và map adapter auto-rank
review             = skill/rank của join review và giới hạn fix rounds
final_assembly     = review.md, final-summary.md, final-artifact.json
```

Luồng hiện tại:

```text
Hermes tạo spec
-> server tạo module tasks từ config
-> scheduler chọn worker profile từ agent-profiles.json
-> worker publish artifact
-> meeting/finalize chỉ tạo fix task cho module failed/missing
-> final assembly ghi durable artifact và validate file output
```

Dashboard có thêm hai vùng nhìn trạng thái:

```text
Guild Event Log   = planned / tasks / claims / artifacts / fixes / final assembly
Meeting Rounds    = round 0 review + các fix round theo module
```

Smoke đã pass:

```text
config scheduler API smoke: worker-a,worker-b,worker-c được chọn từ config
targeted meeting smoke: chỉ module 2 fail thì chỉ tạo build-2-fix-1
provider smoke ngoài sandbox: opencode, openrouter, groq pass
```

Lưu ý: sandbox có thể chặn provider/network path. Provider health nên kiểm bằng normal terminal hoặc Provider Lab; không ghi hoặc commit key từ `_runtime/provider-secrets.local.ps1`.

## 4. Adapter là gì?

Adapter là driver. Worker không nên gọi provider thẳng.

Sai hướng:

```text
worker -> opencode CLI trực tiếp
worker -> OpenRouter API trực tiếp
worker -> Gemini API trực tiếp
```

Đúng hướng:

```text
worker -> adapter interface -> provider/tool cụ thể
```

Vì sao?

Mỗi provider có cách gọi khác nhau, lỗi khác nhau, auth khác nhau, format khác nhau. Adapter chuẩn hóa chúng thành một contract chung.

Adapter runtime hiện nằm ở:

```text
scripts/guild_provider_adapters/
```

Các file:

```text
base.py                 = AdapterContext, AdapterResult, ProviderAdapter
local_dry_run.py        = fake provider để test không tốn tiền
opencode.py             = adapter gọi OpenCode CLI
invalid_output.py       = adapter test output sai schema
registry.py             = chọn adapter theo tên
invoke.py               = CLI entrypoint Python
```

Wrapper PowerShell:

```text
scripts/invoke-guild-provider-adapter.ps1
```

## 5. Provider khác adapter thế nào?

Provider là nguồn thực thi thật:

```text
opencode
OpenRouter
Gemini
Codex
Cerebras
local-dry-run
```

Adapter là lớp điều khiển provider đó.

Ví dụ:

```text
Adapter: opencode
Provider/model: 9router/openrouter/qwen/qwen3-coder:free
CLI thật: opencode run --pure --format json --model 9router/openrouter/qwen/qwen3-coder:free
```

Hiện trạng:

```text
local-dry-run         implemented
opencode              implemented
opencode + provider/model routing implemented
openrouter            selectable, direct adapter chưa implement
gemini                selectable, direct adapter chưa implement
invalid-output-smoke  test-only
```

## 6. Vì sao UI không nên gọi model trực tiếp?

UI là nơi giao task và quan sát. UI không nên giữ logic orchestration.

Sai hướng:

```text
button -> call model -> model làm gì đó -> UI đoán trạng thái
```

Đúng hướng:

```text
button
-> dashboard API
-> create tasks in blackboard
-> wake workers
-> workers claim tasks
-> artifacts
-> dashboard reads blackboard
```

Lý do:

```text
UI reload không mất state
worker có thể chạy ngoài browser
task có audit trail
dashboard chỉ cần đọc state
provider lỗi vẫn lưu evidence
```

Dashboard hiện tại:

```text
docs/incubation/guild-dashboard.html
```

Dashboard API:

```text
scripts/guild-dashboard-server.py
```

Launcher:

```text
scripts/open-guild-dashboard.ps1
```

## 7. Flow UI hiện tại

Bạn nhấn một nút:

```text
Giao Task Cho Hermes
```

UI gửi:

```http
POST /api/quest/manual
```

Server tạo DAG cố định:

```text
spec   -> done ngay, như contract đã approved
build  -> open
test   -> blocked, chờ build
review -> blocked, chờ build + test
```

Sau đó UI tự gọi:

```http
POST /api/wake
```

Workers được wake:

```text
builder
tester
reviewer
```

Dashboard auto-refresh để thấy board đổi trạng thái.

## 8. Bốn cột Blackboard

Board vẫn là 4 section:

```text
Ready    = status open
Claimed  = status claimed/running
Blocked  = status blocked
Done     = status done
```

Nếu bạn thấy “mất”, lý do là panel nhập task phía trên đẩy board xuống. UI đã được nén lại để board hiện rõ hơn.

Code render cột nằm trong:

```text
docs/incubation/guild-dashboard.html
```

Các cột được định nghĩa bằng:

```js
const columnDefs = [
  { id: "ready", title: "Ready", status: "open" },
  { id: "claimed", title: "Claimed", status: "claimed", alt: ["running"] },
  { id: "blocked", title: "Blocked", status: "blocked" },
  { id: "done", title: "Done", status: "done" }
];
```

## 9. Worker chạy thế nào?

Worker terminal không tự “nghĩ lung tung”. Nó chạy loop:

```text
check blackboard
claim task phù hợp rank/skill
build prompt packet nhỏ
call adapter
validate output
publish artifact
mark done/failed
unlock dependents
export dashboard
sleep
repeat
```

Script chính:

```text
scripts/start-guild-worker-terminal.ps1
scripts/run-guild-worker-agent.ps1
```

Điểm cần nhớ:

```text
start-guild-worker-terminal.ps1 = mở terminal/loop
run-guild-worker-agent.ps1      = làm một claim/execution cycle
```

## 10. “Hermes suy nghĩ” trên UI nên hiểu thế nào?

Không nên hiển thị chain-of-thought thật. Cái UI nên hiển thị là progress/routing log:

```text
Received task from Guild Hall.
Applying fixed v0 split rules.
Posting contract/build/test/review tasks to blackboard.
Waking workers automatically after board update.
```

Đó là log vận hành. Nó giúp bạn hiểu hệ thống đang đi tới đâu mà không phụ thuộc vào suy nghĩ ẩn của model.

## 11. Vì sao cần allowed_files?

Đây là luật an toàn.

Task nên có scope:

```text
allowed_files = docs/incubation/*, scripts/*
```

Worker không nên được quyền sửa cả repo nếu task chỉ cần sửa dashboard.

Đây là khác biệt giữa demo “vibecode” và runtime có kỷ luật.

## 12. Vì sao có rank/skill?

Rank/skill giúp worker claim đúng việc:

```text
Builder  = rank C, skill general/ui/app_logic
Tester   = rank B, skill testing
Reviewer = rank B, skill integration_review
Hermes   = rank S, planning/review/orchestration
```

Profile nằm ở:

```text
config/guild/agent-profiles.json
docs/workers/AGENT_PROFILES.md
```

## 13. Vì sao phải có blocked_reason?

Không phải “blocked” nào cũng giống nhau.

Ví dụ:

```text
waiting_dependencies
plan_review_pending
human_approval_required
provider_error_event
adapter_not_implemented
invalid_adapter_output
```

Nếu không có `blocked_reason`, bạn chỉ thấy task đứng yên mà không biết vì sao.

## 14. Flock nằm ở đâu?

Flock là candidate/framework cho orchestration typed-agent, nhưng hiện dashboard/control path chưa full Flock-native.

Hiện tại live runtime chủ yếu là:

```text
Pydantic models
SQLite
PowerShell scripts
Python adapter runtime
Static dashboard + local API server
```

Flock vẫn hữu ích làm hướng runtime sau này, nhưng Guild-specific semantics phải tự định nghĩa:

```text
rank/skill claim
allowed_files
blocked_reason
artifact evidence
provider adapter policy
dashboard read model
Windows terminal wake
```

## 15. Những file bạn nên đọc theo thứ tự

Nếu muốn hiểu dự án, đọc theo thứ tự này:

```text
START_HERE.md
PROJECT_CONTEXT.md
TASKS.md
docs/architecture/HERMES_COGNITIVE_OS_BLUEPRINT.md
docs/architecture/HERMES_GUILD_SYSTEM_THOUGHTS.md
docs/workers/WORKER_BOOTSTRAP.md
docs/workers/AGENT_PROFILES.md
docs/workers/PROVIDER_ADAPTERS.md
scripts/README.md
```

Sau đó mới đọc code:

```text
docs/incubation/guild-dashboard.html
scripts/guild-dashboard-server.py
scripts/run-guild-worker-agent.ps1
scripts/start-guild-worker-terminal.ps1
scripts/invoke-guild-provider-adapter.ps1
scripts/guild_provider_adapters/base.py
scripts/guild_provider_adapters/opencode.py
_runtime/flock/worker_team_prototype.py
```

## 16. Những câu hỏi senior luôn hỏi

Khi thêm feature mới, hỏi:

```text
State nằm ở đâu?
Có restart-safe không?
Output có schema không?
Lỗi provider đi đâu?
Task có evidence không?
Có mark done giả không?
UI là source of truth hay chỉ là view?
Secret có bị ghi vào repo không?
Worker có bị quyền quá rộng không?
Có smoke test deterministic trước khi gọi model tốn tiền không?
```

Nếu trả lời được mấy câu này, bạn đã bắt đầu nghĩ như người thiết kế runtime.

## 17. Trạng thái hiện tại

Đã có:

```text
blackboard task/artifact
dashboard 4 cột
UI giao task
manual fixed DAG split
auto wake route
worker-agent loop
adapter runtime
opencode adapter
output validation
invalid-output negative smoke
```

Chưa xong:

```text
real UI wake full smoke với terminal thật
direct OpenRouter adapter
direct Gemini adapter
blocked/needs-info artifact type chuẩn
opencode token/context optimization
production Guild app/API
```

## 18. Bài học lớn nhất

Bạn đang xây một hệ thống lớn, nên cảm giác bị ngợp là bình thường. Điểm quan trọng không phải nhớ hết syntax. Điểm quan trọng là giữ được kiến trúc:

```text
UI chỉ giao task và nhìn state.
Blackboard giữ state.
Worker claim task.
Adapter gọi tool/provider.
Artifact là bằng chứng.
Validator chặn output bậy.
Dashboard đọc state, không đoán.
```

Syntax có thể tra. Kiến trúc và ranh giới mới là phần khó.

## 19. Giáo trình đọc code: nhìn code theo lớp

Khi đọc code của dự án này, đừng đọc từ trên xuống hết file. Đọc theo đường dữ liệu.

Một request đi qua các lớp:

```text
HTML button
-> fetch("/api/quest/manual")
-> Python dashboard server
-> worker_team_prototype.py create-task
-> SQLite guild_tasks
-> fetch("/api/wake")
-> start-guild-worker-terminal.ps1
-> run-guild-worker-agent.ps1
-> invoke-guild-provider-adapter.ps1
-> Python adapter runtime
-> provider/tool
-> artifact JSON
-> publish-artifact
-> dashboard refresh
```

Đọc code theo flow này sẽ dễ hơn đọc theo file.

## 20. Code UI: `guild-dashboard.html`

File:

```text
docs/incubation/guild-dashboard.html
```

### Một nút giao task

Code chính nằm trong handler:

```js
el("questForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    title: el("questTitle").value,
    request: el("questRequest").value,
    quest_chain_id: el("questId").value,
    allowed_files: el("questAllowed").value,
    adapter: el("questAdapter").value
  };
  ...
});
```

Ý nghĩa:

- `event.preventDefault()` chặn browser reload page khi submit form.
- `payload` là JSON request gửi xuống local API.
- UI không tự tạo task trong browser. Nó giao việc cho server.

Vì sao làm vậy:

- Browser không phải source of truth.
- State phải nằm trong SQLite blackboard.
- Nếu reload browser, task vẫn còn.

### Gọi API tạo quest

```js
const response = await fetch("/api/quest/manual", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
});
```

Ý nghĩa:

- `fetch` gọi local dashboard server.
- `Content-Type: application/json` nói với server rằng body là JSON.
- `JSON.stringify(payload)` biến object JavaScript thành string JSON.

Kinh nghiệm senior:

> UI gửi command dạng JSON. Server mới là nơi mutate state.

### Tự wake worker sau khi tạo quest

```js
const wakeResponse = await fetch("/api/wake", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    quest_chain_id: value.quest_chain_id,
    adapter: el("questAdapter").value,
    profiles: ["builder", "tester", "reviewer"]
  })
});
```

Ý nghĩa:

- Sau khi task đã vào blackboard, UI gọi wake.
- Wake không phải nút riêng nữa.
- Worker được chọn theo profile.

Vì sao không wake trước?

Vì worker claim task từ blackboard. Nếu chưa có task trong DB thì wake cũng không có gì để claim.

### Render bốn cột

```js
const columnDefs = [
  { id: "ready", title: "Ready", status: "open" },
  { id: "claimed", title: "Claimed", status: "claimed", alt: ["running"] },
  { id: "blocked", title: "Blocked", status: "blocked" },
  { id: "done", title: "Done", status: "done" }
];
```

Ý nghĩa:

- UI không đoán task nên nằm cột nào.
- Nó nhìn `task.status`.
- `open` vào Ready, `blocked` vào Blocked, `done` vào Done.

Kinh nghiệm senior:

> UI nên là projection từ state, không phải nơi tự nghĩ business logic phức tạp.

## 21. Code API server: `guild-dashboard-server.py`

File:

```text
scripts/guild-dashboard-server.py
```

Thư viện dùng:

```python
argparse
json
os
subprocess
time
urllib.parse
http.server
pathlib
typing
```

Đây đều là thư viện chuẩn của Python, không cần install package ngoài.

### Vì sao dùng `http.server`?

Vì demo local cần một server nhỏ:

```text
serve HTML
nhận POST từ UI
gọi script backend
trả JSON
```

Không cần FastAPI/Flask ngay vì:

- giảm dependency
- dễ chạy trên máy local
- đủ cho incubator demo

Sau này production hơn thì có thể đổi sang FastAPI.

### Health check

```python
if parsed.path == "/api/health":
    self.send_json({
        "ok": True,
        "service": "guild-dashboard",
        "version": "0.2",
        "workspace": str(self.workspace),
        "db_path": self.db_path,
    })
```

Ý nghĩa:

- UI/launcher biết server còn sống.
- `version` giúp biết server mới hay cũ.
- `db_path` giúp tránh bug server cũ dùng sai SQLite DB.

Bug đã gặp:

```text
server cũ trên port 8765 trả health OK
nhưng dùng DB path sai
```

Cách fix senior:

```text
health check không chỉ trả ok=true
health check phải trả đủ identity/config quan trọng
```

### Tạo quest manual

```python
def handle_manual_quest(self, body):
    title = str(body.get("title") or "Manual guild quest").strip()
    request = str(body.get("request") or "").strip()
    if not request:
        raise ValueError("request is required")
```

Ý nghĩa:

- Server parse JSON body.
- `request` là bắt buộc.
- Fail sớm nếu thiếu input quan trọng.

Kinh nghiệm senior:

> Validate input ở boundary. Đừng để dữ liệu hỏng đi sâu vào runtime.

### Build fixed DAG

```python
plan = build_manual_plan(quest_chain_id, title, request, allowed_files)
```

Hiện chưa cần Hermes tự nghĩ. Ta dùng rule cố định:

```text
spec -> build -> test -> review
```

Vì sao:

- demo ổn định
- ít magic
- dễ debug
- đúng yêu cầu hiện tại: bạn split/rule sẵn trước

### Gọi subprocess

```python
completed = self.run_cmd(args)
if completed.returncode != 0:
    raise RuntimeError(...)
```

Ý nghĩa:

- Python server gọi CLI backend.
- Nếu CLI fail, API trả lỗi rõ.

Kinh nghiệm senior:

> Khi gọi process ngoài, luôn check exit code. Không check exit code là nguồn bug rất lớn.

### Vì sao xóa `PYTHONHOME/PYTHONPATH`?

```python
env = os.environ.copy()
env.pop("PYTHONHOME", None)
env.pop("PYTHONPATH", None)
```

Bug đã gặp:

```text
SRE module mismatch
```

Nguyên nhân:

- Python parent process có environment không sạch.
- Subprocess dùng venv Python nhưng bị lẫn path của Python khác.

Fix:

- Khi gọi Python subprocess, bỏ `PYTHONHOME` và `PYTHONPATH`.

Kinh nghiệm senior:

> Bug môi trường thường không nằm ở code logic. Nó nằm ở process/env/path.

## 22. Code worker: `run-guild-worker-agent.ps1`

File:

```text
scripts/run-guild-worker-agent.ps1
```

Đây là trái tim của worker execution.

Flow chính:

```text
load profile
claim task
build prompt packet
call adapter
parse adapter result
validate artifact JSON
publish artifact
mark done/failed
unlock dependents
```

### Claim task

```powershell
$claimArgs = @(
    $guild,
    "claim-next",
    "--agent-id", $profileData.agent_id,
    "--agent-rank", $profileData.rank,
    "--skills", $profileData.skills,
    "--lease-seconds", $LeaseSeconds,
    "--scan-limit", $ScanLimit
)
```

Ý nghĩa:

- Worker không tự chọn bừa task.
- Nó gọi blackboard để claim task phù hợp.
- Rank/skill quyết định claim được hay không.

Kinh nghiệm senior:

> Task ownership nên được quyết định bởi queue/blackboard, không phải bằng prompt tự do.

### Build prompt packet

```powershell
$message = @"
You are a HermesGuildCore Guild worker.
...
Current GuildTask JSON:
$taskJson
...
"@
```

Ý nghĩa:

- Adapter/provider nhận task contract rõ.
- Prompt có shape output bắt buộc.
- Không load cả repo vào prompt.

Kinh nghiệm senior:

> Prompt tốt là prompt có contract, scope, và expected output. Không phải prompt dài vô hạn.

### Call adapter

```powershell
$adapterRaw = & $adapterScript @adapterArgs
$adapterResult = $adapterRaw | ConvertFrom-Json
```

Ý nghĩa:

- PowerShell gọi adapter wrapper.
- Output phải là JSON để parse.

Vì sao adapter wrapper cần JSON?

- PowerShell object và Python object khác nhau.
- JSON là format trung gian ổn định.

### Validate output

```powershell
$artifactValidation = Test-GuildArtifactOutput -AdapterResult $adapterResult
```

Ý nghĩa:

- Adapter báo `ok=true` chưa đủ.
- `adapter_result.text` phải là artifact JSON hợp lệ.

Nếu không validate, model có thể trả:

```json
{"ok": true}
```

và runtime tưởng đã xong.

Validator chặn chuyện đó.

### Publish artifact

```powershell
$publish = Invoke-GuildCliJson -Arguments @(
    $guild,
    "publish-artifact",
    "--task-id", $task.task_id,
    "--artifact-type", $task.output_artifact,
    "--producer-agent-id", $profileData.agent_id,
    "--summary", $summary,
    "--payload-json-file", $payloadPath
)
```

Ý nghĩa:

- Kết quả không chỉ in ra terminal.
- Nó được lưu vào blackboard.
- Dashboard/reviewer có thể đọc lại.

Kinh nghiệm senior:

> “Done” mà không có artifact/evidence thì chưa đáng tin.

## 23. Code adapter runtime

Folder:

```text
scripts/guild_provider_adapters/
```

### Base contract

```python
@dataclass(frozen=True)
class AdapterContext:
    adapter_name: str
    adapter_config: dict[str, Any]
    profile_name: str
    agent_profile: dict[str, Any]
    message: str
    title: str
    workspace: str
    provider: str | None = None
    model: str | None = None
```

Ý nghĩa:

- Context chứa mọi thứ adapter cần biết.
- Không truyền 10 biến rời rạc.
- `frozen=True` nghĩa là object không nên bị mutate sau khi tạo.

Kinh nghiệm senior:

> Gom input thành context object giúp interface ổn định khi hệ thống lớn dần.

### AdapterResult

```python
@dataclass
class AdapterResult:
    ok: bool
    adapter: str
    profile: str
    agent_id: str | None
    summary: str
    text: str = ""
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    test_result: str = "not_run"
    known_risks: list[Any] = field(default_factory=list)
    blocked_reason: str | None = None
```

Ý nghĩa:

- Đây là output chung của mọi adapter.
- Dù provider là opencode hay Gemini, runtime nhận cùng shape.

Vì sao `default_factory=list`?

Sai:

```python
files_changed: list[str] = []
```

Lý do sai:

- list mutable có thể bị share giữa instances.

Đúng:

```python
files_changed: list[str] = field(default_factory=list)
```

Đây là một kinh nghiệm Python rất thực tế.

### Registry

```python
def get_adapter(name: str) -> ProviderAdapter:
    if name == "local-dry-run":
        return LocalDryRunAdapter()
    if name == "invalid-output-smoke":
        return InvalidOutputAdapter()
    if name in {"opencode", "opencode-9router"}:
        return OpenCodeAdapter()
    return UnimplementedAdapter()
```

Ý nghĩa:

- Runtime chọn adapter theo tên.
- Adapter chưa có vẫn trả structured result.
- Không crash bừa.

Kinh nghiệm senior:

> Unknown/unsupported path cũng nên là một state có cấu trúc, không phải stacktrace nếu có thể tránh.

## 24. Code OpenCode adapter

File:

```text
scripts/guild_provider_adapters/opencode.py
```

### Tìm executable

```python
executable = shutil.which("opencode")
if not executable:
    return AdapterResult(... blocked_reason="provider_missing")
```

Ý nghĩa:

- Kiểm tra tool có tồn tại không.
- Nếu thiếu thì trả blocked result.

Kinh nghiệm senior:

> Dependency missing là trạng thái dự đoán được, không nên thành lỗi bí ẩn.

### Build args

```python
args = [
    executable,
    "run",
    "--pure",
    "--format",
    "json",
    "--title",
    context.title,
]
```

Ý nghĩa:

- Không dùng string command dài.
- Dùng list args để tránh bug quoting.

Vì sao quan trọng trên PowerShell/Windows?

- JSON trong prompt có dấu `{}`, `"`, `:` rất dễ làm shell tách sai.
- `subprocess.run(args)` an toàn hơn string command.

### Provider/model routing

```python
if context.provider:
    return f"{context.provider}/{context.model}"
```

Ví dụ:

```text
provider = 9router
model = openrouter/qwen/qwen3-coder:free
-> 9router/openrouter/qwen/qwen3-coder:free
```

Đó là model ref mà OpenCode hiểu.

### Parse event stream

OpenCode không trả một JSON object duy nhất. Nó trả nhiều event JSON lines.

Adapter làm việc này:

```text
đọc từng line
json.loads(line)
lấy text event
lấy error event
lấy sessionID
lấy token usage
```

Kinh nghiệm senior:

> Tool output thường không cùng shape với runtime cần. Adapter là nơi normalize.

## 25. Quy trình smoke test chuẩn

Smoke test là test nhỏ để biết “đường dây còn sống không”.

Không phải test toàn bộ sản phẩm.

Quy trình chuẩn:

```text
1. Test layer nhỏ nhất
2. Test adapter không tốn tiền
3. Test worker-agent với local-dry-run
4. Test negative path
5. Test UI/API
6. Chỉ sau đó mới test provider thật
```

Ví dụ:

### Test adapter local

```powershell
python -B scripts\guild_provider_adapters\invoke.py `
  --adapter local-dry-run `
  --profile builder `
  --message "syntax smoke"
```

Mục tiêu:

```text
Python import OK
adapter registry OK
JSON output OK
```

### Test negative output

```powershell
python -B scripts\guild_provider_adapters\invoke.py `
  --adapter invalid-output-smoke `
  --profile builder `
  --message "invalid smoke"
```

Mục tiêu:

```text
adapter cố tình trả output sai
worker validator phải bắt được
```

### Test worker-agent

```powershell
.\scripts\run-guild-worker-agent.ps1 `
  -Profile builder `
  -Adapter local-dry-run `
  -QuestChainId demo-visible-handoff-v2 `
  -TaskId smoke-visible-local-agent-v2 `
  -Json
```

Mục tiêu:

```text
claim task
adapter returns artifact JSON
validation valid=true
publish artifact
mark done
```

### Test UI API

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8780/api/health'
```

Mục tiêu:

```text
server alive
version đúng
workspace đúng
db_path đúng
```

### Test provider thật

Chỉ làm sau các test trên:

```powershell
.\scripts\configure-guild-worker.ps1 `
  -Profile builder `
  -Adapter opencode `
  -TestNow
```

Vì provider thật có các biến nhiễu:

```text
auth
quota
network
token cost
sandbox permission
tool version
```

## 26. Vì sao GPT có thể tự test/sửa tốt hơn model yếu?

Không phải vì GPT “biết phép thuật”. Nó làm theo loop kỹ thuật chuẩn:

```text
observe
form hypothesis
make minimal change
run targeted test
read error
adjust
record finding
```

Ví dụ bug stale server:

```text
Symptom:
  /api/health ok nhưng /api/quest/manual lỗi DB

Hypothesis:
  port đang chạy server cũ

Fix:
  health trả thêm version/workspace/db_path
  launcher reject stale server nếu db_path sai

Test:
  start server port mới
  GET /api/health
  POST /api/quest/manual
```

Model yếu thường fail vì:

```text
đọc thiếu context
không chạy test
thấy error nhưng không truy nguyên
fix quá rộng
không phân biệt symptom/root cause
không giữ state trong đầu
```

Bạn có thể học quy trình này. Không cần học hết syntax trước.

Template debug:

```text
1. Tôi vừa thấy lỗi gì?
2. Lỗi xảy ra ở layer nào? UI/API/worker/adapter/provider/DB?
3. Input vào layer đó là gì?
4. Output mong đợi là gì?
5. Có test nhỏ hơn để cô lập không?
6. Fix nhỏ nhất là gì?
7. Chạy lại test nào để chứng minh?
8. Ghi finding vào đâu?
```

## 27. Các thư viện/công cụ phổ biến đang dùng

Python standard library:

```text
argparse       parse CLI args
json           encode/decode JSON
subprocess     gọi command/script ngoài
http.server    local HTTP server
pathlib        xử lý path
dataclasses    data object nhẹ
typing         type hints
shutil.which   tìm executable
sqlite3        SQLite DB
```

Python external:

```text
pydantic       validate model/schema trong prototype
flock          orchestration candidate/research runtime
```

PowerShell:

```text
Invoke-RestMethod  gọi HTTP API
Start-Process      mở server/terminal
ConvertTo-Json     object -> JSON
ConvertFrom-Json   JSON -> object
Test-Path          kiểm tra file
Resolve-Path       canonical path
```

Frontend:

```text
HTML form
CSS grid/flex
fetch API
JSON.stringify / response.json
DOM event listener
```

CLI/tools:

```text
opencode
Everything ES
rg
fd
bat
eza
git
```

## 28. Cách tự học codebase này trong 7 ngày

Ngày 1:

```text
Đọc file này.
Chạy dashboard.
Nhìn 4 cột và task status.
```

Ngày 2:

```text
Đọc guild-dashboard.html.
Hiểu fetch /api/quest/manual và /api/wake.
```

Ngày 3:

```text
Đọc guild-dashboard-server.py.
Hiểu subprocess và create-task.
```

Ngày 4:

```text
Đọc run-guild-worker-agent.ps1.
Hiểu claim -> adapter -> artifact -> done/failed.
```

Ngày 5:

```text
Đọc adapter runtime.
Hiểu AdapterContext và AdapterResult.
```

Ngày 6:

```text
Chạy smoke local-dry-run.
Chạy invalid-output-smoke.
So sánh success path và failure path.
```

Ngày 7:

```text
Thử opencode adapter.
Ghi lại provider/auth/token/sandbox issue.
```

Mục tiêu sau 7 ngày không phải thuộc syntax. Mục tiêu là nhìn một bug và biết nó thuộc layer nào.
