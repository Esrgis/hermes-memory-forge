 Tổng Luồng
  UI hiện đi theo pipeline này:

  User prompt
  -> Plan Preview
  -> Create Quest/Tasks
  -> Wake Workers
  -> Worker Agent Loop
  -> Provider Adapter
  -> Artifact JSON Validation
  -> Grounding/File Scope/File Write
  -> Publish Artifact + Set Task Status
  -> Unlock Review
  -> Reviewer Agent
  -> Finalizer
  -> UI Dashboard

  1. User Prompt
  Input:

  Prompt bạn nhập trong UI
  Adapter choice: auto-rank / local-file-writer / ...

  Output:

  {
    "request": "...",
    "adapter": "auto-rank"
  }

  Điểm owner:

  - Bạn đang owner prompt/task shape.
  - Runtime chưa nên tự hiểu quá nhiều ở bước này.

  2. Plan Preview
  Node:

  /api/hermes/plan-preview

  Input:

  {
    "request": "Make a one-hour Guild demo...",
    "adapter": "auto-rank"
  }

  Output:

  {
    "template": "three-part-local-demo",
    "task_count": 4,
    "tracks": [
      "data model",
      "render UI",
      "interaction notes",
      "review"
    ]
  }

  Nó sinh file:

  guild-workspaces/<quest>/hermes-plan.json
  guild-workspaces/<quest>/task-brief.md

  Risk:

  - Nếu template tự nhét từ như one-hour, Hermes, Guild, guard phía sau có thể bắt từ đó.

  3. Create Quest
  Node:

  /api/hermes/quest

  Input:

  {
    "plan": "hermes-plan.json"
  }

  Output trong DB:

  task-1: execution, requirements, output build-1.md
  task-2: execution, risk-analysis, output build-2.md
  task-3: execution, verification, output build-3.md
  review: join_review, depends_on task-1/task-2/task-3

  Mỗi task có:

  {
    "task_id": "...task-2",
    "task_type": "execution",
    "required_skill": "risk-analysis",
    "allowed_files": "guild-workspaces/<quest>/**",
    "request": "...",
    "depends_on": [...]
  }

  Điểm owner:

  - Runtime owner task graph.
  - Bạn owner việc template có hợp lý không.

  4. Wake Workers
  Node:

  /api/wake

  Input:

  {
    "quest_chain_id": "...",
    "profiles": ["worker-a", "worker-b", "worker-c", "reviewer"],
    "adapter": "auto-rank"
  }

  Output:

  {
    "worker-a": "gemini:gemini-2.5-flash",
    "worker-b": "opencode:deepseek-v4-flash-free",
    "worker-c": "openrouter:poolside-laguna-free",
    "reviewer": "groq:gpt-oss-20b"
  }

  Nó tạo worker loop:

  _runtime/guild-worker-agent/terminal-sessions/<quest-worker>/worker-loop.ps1

  Điểm owner:

  - Runtime owner routing.
  - UI chỉ hiển thị route, không phải truth.

  5. Worker Agent Loop
  Node:

  start-guild-worker-terminal.ps1
  -> run-guild-worker-agent.ps1

  Mỗi vòng loop:

  check stop marker
  claim-next
  if claimed -> call provider
  export dashboard
  sleep 2s

  Input:

  {
    "profile": "worker-b",
    "quest_chain_id": "...",
    "provider": "opencode:deepseek-v4-flash-free"
  }

  Output nếu không có task:

  {
    "claimed": false,
    "reason": "no_claimable_task"
  }

  Output nếu stop:

  {
    "claimed": false,
    "reason": "quest_stop_requested"
  }

  Điểm owner:

  - Runtime owner lifecycle.
  - Bug vừa rồi: Stop Run chỉ cancel DB, loop vẫn chạy. Đã thêm stop marker.

  6. Claim Task
  Node:

  guild-worker-team.py claim-next

  Input:

  {
    "agent_id": "worker-b",
    "skills": "risk-analysis,...",
    "quest_chain_id": "...",
    "scan_limit": 50
  }

  Output:

  {
    "claimed": true,
    "task": {
      "task_id": "...task-2",
      "request": "...",
      "allowed_files": "...",
      "depends_on": [...]
    }
  }

  Claim chỉ lấy task:

  status = open
  rank đủ
  skill khớp
  dependency done

  Điểm owner:

  - Runtime owner scheduling.
  - Agent chưa “tư duy” gì ở đây.

  7. Build Provider Prompt
  Node:

  run-guild-worker-agent.ps1

  Input:

  {
    "task": "GuildTask JSON",
    "profile": "worker-b",
    "visible_scope": "task_only | join_review"
  }

  Prompt gửi provider gồm:

  NON-INTERACTIVE EXECUTION
  Agent profile
  Context envelope
  Scope rules
  Quality gates
  Current GuildTask JSON
  Return only compact artifact JSON

  Sau patch, nếu join_review, prompt còn có:

  Visible upstream context:
  - task-brief.md
  - build-1.md
  - build-2.md
  - build-3.md

  Điểm owner:

  - Runtime owner prompt contract.
  - Provider chỉ làm theo contract.
  - Nếu runtime không đưa upstream context thì reviewer fail là đúng.

  8. Provider Adapter
  Node:

  invoke-guild-provider-adapter.ps1
  -> guild_provider_adapters/*

  Input:

  {
    "adapter": "auto-ammo",
    "provider": "groq:gpt-oss-20b",
    "message": "full worker prompt"
  }

  Output adapter chuẩn:

  {
    "ok": true,
    "summary": "...",
    "text": "{ artifact JSON string }",
    "commands_run": [...],
    "tokens": {...},
    "blocked_reason": null
  }

  Provider text phải là artifact JSON:

  {
    "ok": true,
    "summary": "Wrote build-2.md...",
    "files_changed": [
      "guild-workspaces/<quest>/build-2.md"
    ],
    "file_outputs": [
      {
        "path": "guild-workspaces/<quest>/build-2.md",
        "content": "actual markdown..."
      }
    ],
    "commands_run": [],
    "test_result": "not_required",
    "known_risks": [],
    "blocked_reason": null
  }

  Điểm owner:

  - Adapter owner provider call.
  - Worker agent owner validate output.
  - Provider không đáng tin tuyệt đối.

  9. Adapter Output Validation
  Node:

  Test-GuildArtifactOutput

  Input:

  adapter_result.text

  Checks:

  is JSON
  has required fields
  summary non-empty
  files_changed array
  commands_run array
  known_risks array
  if task terms expected then present

  Output:

  {
    "valid": true,
    "output": {
      "ok": true,
      "summary": "...",
      "files_changed": [...]
    }
  }

  Fail ví dụ:

  {
    "valid": false,
    "blocked_reason": "invalid_adapter_output",
    "errors": ["Missing required artifact field: files_changed"]
  }

  Điểm owner:

  - Guard này cần thiết.
  - Nhưng nếu guard nhìn keyword quá nhiều ở đây thì dễ false negative.

  10. Grounding Validation
  Node:

  Test-GuildArtifactGrounding

  Input:

  {
    "worker_output": "...",
    "task": "GuildTask",
    "workspace": "D:\\HermesGuildCore"
  }

  Nó gom text từ:

  summary
  blocked_reason
  file_outputs.content
  files_changed content trên disk nếu có

  Checks hiện có:

  output không rỗng
  output đủ dài
  nếu request có Guild -> output có guild
  nếu request có Hermes -> output có hermes/hermesguildcore/guild
  nếu request có one-hour -> output có one-hour/one hour/hour/demo/guild demo
  nếu skill requirements -> có requirements/requirement
  nếu skill risk -> có risk/risks/mismatch/integration concern
  nếu skill verification -> có verification/verify/acceptance evidence
  nếu join_review -> có review.md/final-summary.md/integration review/join review
  placeholder file output phải có file thật trên disk đủ dài

  Output:

  {
    "valid": true,
    "blocked_reason": null
  }

  Hoặc:

  {
    "valid": false,
    "blocked_reason": "ungrounded_artifact_output",
    "errors": ["Artifact is not grounded in required anchor: one-hour."]
  }

  Điểm owner:

  - Đây là chỗ bạn đang mất owner nhiều nhất.
  - Guard này đang encode “thế nào là output đúng”.
  - Nên tách thành:
      - hard guard: file thật, scope đúng, schema đúng
      - soft guard: keyword/semantic warning

  11. File Scope Validation
  Node:

  Test-DeclaredFilesWithinAllowedScope

  Input:

  {
    "files_changed": ["guild-workspaces/<quest>/build-2.md"],
    "allowed_files": "guild-workspaces/<quest>/**"
  }

  Checks:

  không absolute path
  không ..
  phải nằm trong allowed_files

  Output:

  {
    "valid": true
  }

  Điểm owner:

  - Nên giữ cứng. Đây là safety boundary.

  12. File Write
  Node:

  Write-GuildWorkerFileOutputs

  Input:

  {
    "file_outputs": [
      {
        "path": "guild-workspaces/<quest>/build-2.md",
        "content": "actual markdown"
      }
    ]
  }

  Output:

  {
    "ok": true,
    "written": ["guild-workspaces/<quest>/build-2.md"]
  }

  Sau patch:

  Nếu content là "See file written directly to disk..."
  -> không overwrite file thật.
  -> nếu file thật đủ nội dung trên disk, accept.
  -> nếu không có file thật, fail.

  Điểm owner:

  - Runtime owner durable artifact.
  - Đây nên là hard guard.

  13. Publish Artifact
  Node:

  guild-worker-team.py publish-artifact

  Input:

  {
    "task_id": "...task-2",
    "artifact_type": "implementation_result_2",
    "payload_json_file": "_runtime/guild-worker-agent/...payload.json"
  }

  Output DB artifact:

  {
    "artifact_id": "...",
    "task_id": "...task-2",
    "summary": "agent_worker-b_completed_..."
  }

  Điểm owner:

  - Runtime owner blackboard evidence.
  - UI đọc cái này.

  14. Set Status
  Node:

  guild-worker-team.py set-status

  Input:

  task_id, done|failed|blocked

  Decision:

  artifactOk true -> done
  artifactOk false + needs_info -> blocked
  artifactOk false -> failed

  Output:

  {
    "task_id": "...",
    "status": "done"
  }

  Điểm owner:

  - Đây là nơi hiện đang quá thô.
  - Cần failure classifier để không mọi thứ thành failed đỏ chung.

  15. Unlock Review
  Node:

  guild-worker-team.py unlock-ready

  Input:

  DB tasks

  Logic:

  Nếu task blocked/open có dependencies đều done -> open

  Review chỉ open khi:

  task-1 done
  task-2 done
  task-3 done

  Output:

  {
    "unlocked": ["...review"]
  }

  Điểm owner:

  - Runtime owner dependency graph.
  - Nếu worker false failed thì review không bao giờ chạy.
  - Nếu worker false done với file rác thì review chạy rồi fail.

  16. Reviewer Agent
  Same worker path, nhưng:

  {
    "task_type": "join_review",
    "visible_scope": "join_review",
    "depends_on": ["task-1", "task-2", "task-3"]
  }

  Input sau patch:

  GuildTask JSON
  task-brief.md content
  build-1.md content
  build-2.md content
  build-3.md content

  Expected output:

  {
    "ok": true,
    "summary": "Reviewed module outputs...",
    "files_changed": [
      "guild-workspaces/<quest>/review.md",
      "guild-workspaces/<quest>/final-summary.md"
    ],
    "file_outputs": [
      {
        "path": "guild-workspaces/<quest>/review.md",
        "content": "..."
      },
      {
        "path": "guild-workspaces/<quest>/final-summary.md",
        "content": "..."
      }
    ],
    "commands_run": [],
    "test_result": "not_required",
    "known_risks": [],
    "blocked_reason": null
  }

  Điểm owner:

  - Reviewer không nên tự đọc filesystem tùy ý.
  - Runtime phải cung cấp upstream context bounded.
  - Nếu thiếu file upstream, runtime nên block trước provider call, không tốn token.

  17. Finalizer
  Node:

  /api/hermes/finalize

  Input:

  review.md
  final-summary.md
  worker outputs

  Output:

  final-artifact.json

  Nếu thiếu:

  {
    "ready": false,
    "reason": "missing_join_review_outputs"
  }

  Điểm owner:

  - Finalizer không nên chữa worker outputs.
  - Nó chỉ đóng gói khi artifacts đã hợp lệ.

  18. UI Dashboard
  Reads:

  _runtime/dashboard/guild-dashboard.json
  _runtime/dashboard/guild-events.jsonl
  _runtime/guild-worker-agent/*payload.json
  guild-workspaces/<quest>/*

  UI displays:

  task status
  terminal sessions
  provider routes
  files/artifacts

  Risk:

  - UI là display state, không phải source of truth.
  - Truth là DB + payload JSON + workspace files + events.

  Tóm Lại Owner Boundary
  Bạn nên nghĩ thế này:

  User/UI owner:
  - prompt
  - adapter choice
  - when to stop
  - acceptance expectation

  Planner owner:
  - split task graph
  - output file contract
  - dependencies

  Scheduler owner:
  - claim-next
  - dependency unlock
  - stop lifecycle

  Worker agent runtime owner:
  - provider prompt contract
  - schema validation
  - allowed_files
  - durable file write
  - publish artifact
  - status transition

  Provider/model owner:
  - produce actual artifact content

  Reviewer owner:
  - integration judgment from upstream files

  Finalizer owner:
  - package final result only after review success

  Chỗ Nên Siết
  Hard guard nên giữ:

  schema JSON đúng
  allowed_files đúng
  không path traversal
  file thật tồn tại
  file content không placeholder
  reviewer có upstream context trước khi gọi provider
  stop marker không cho worker publish sau stop

  Chỗ Nên Nới
  Soft guard, không nên fail cứng:

  Hermes/Guild keyword
  one-hour/hour keyword
  risk/verification keyword nếu file có nội dung rõ
  summary wording

  Thiết Kế Tốt Hơn
  Tách thành 3 lớp:

  Contract Guard:
  - schema
  - path
  - file durability
  - required output files

  Quality Lint:
  - grounded terms
  - module relevance
  - suspicious generic output

  Supervisor Decision:
  - pass
  - pass_with_warnings
  - retry_same_provider
  - retry_fallback_provider
  - create_fix_task
  - fail_terminal

  Hiện tại mình đang trộn cả 3 vào một artifactOk, nên nó dễ fail và bạn mất owner vì mọi heuristic đều thành luật cứng.