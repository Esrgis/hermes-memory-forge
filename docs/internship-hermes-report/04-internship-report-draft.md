# Internship Report Draft

## Tên Đề Tài Tạm

Xây dựng hệ thống trợ lý AI local-first có bộ nhớ ngữ nghĩa, blackboard runtime và quy trình duyệt nội dung bằng con người.

## Bối Cảnh

Trong quá trình thực tập, tôi xây dựng một hệ thống thử nghiệm xoay quanh Hermes, Obsidian, SQLite, n8n và các công cụ CLI. Mục tiêu không phải tạo một chatbot đơn lẻ, mà là thử nghiệm kiến trúc trợ lý AI có khả năng ghi nhớ có chọn lọc, điều phối tác vụ, lưu trạng thái runtime, và hỗ trợ workflow có human approval.

Hệ thống được phát triển theo hướng local-first: dữ liệu chính nằm trên máy cá nhân, memory dài hạn lưu trong Obsidian, runtime state lưu bằng SQLite, và các hành động được thực hiện qua script có thể kiểm tra lại.

## Mục Tiêu

Các mục tiêu chính:

- Thiết kế memory pipeline cho trợ lý AI.
- Xây dựng blackboard runtime để lưu task/event/decision.
- Thử nghiệm mô hình multi-agent/Guild ở mức prototype.
- Tạo dashboard quan sát task/artifact.
- Tích hợp provider adapter cho nhiều backend model.
- Thử nghiệm n8n làm workflow orchestrator.
- Xây dựng MVP content factory tạo nội dung TikTok/Shorts có bước duyệt qua Telegram.

## Công Nghệ Sử Dụng

- Python
- PowerShell
- SQLite
- Obsidian Markdown vault
- n8n
- Telegram Bot API
- Node.js / npm
- Flock research prototype
- OpenCode / OpenRouter / Groq / Gemini provider experiments
- Local CLI tools: rg, fd, Everything ES, bat, eza

## Kiến Trúc Tổng Quan

Hệ thống được chia thành các lớp:

- Obsidian: lưu memory dài hạn và daily notes.
- SQLite: lưu trạng thái runtime như queue, task, artifact, approval.
- Hermes: xử lý reasoning, routing, memory lookup, content generation.
- n8n: xử lý schedule, trigger, Telegram notification, orchestration đơn giản.
- Guild runtime: prototype cho blackboard task/artifact và worker orchestration.
- Scripts: lớp deterministic automation để dễ debug.

Việc tách các lớp này giúp hệ thống không phụ thuộc hoàn toàn vào một model AI, đồng thời giảm nguy cơ mất kiểm soát khi workflow phức tạp.

## Các Hạng Mục Đã Thực Hiện

### 1. Memory System

Tôi thiết kế memory theo 3 tầng:

- hot memory cho thông tin ngắn hạn/cần dùng thường xuyên
- vault living files cho tri thức ổn định
- daily notes cho timeline/audit log

Tôi cũng xây dựng quy trình truy vấn memory bằng Obsidian FTS để các model yếu vẫn có thể tìm lại thông tin bằng route rõ ràng thay vì dựa vào context dài.

### 2. Blackboard Runtime

Tôi tạo blackboard SQLite để lưu:

- tasks
- events
- decisions
- memory candidates
- workflow runs
- checkins
- current state
- agent status

Blackboard này là nền tảng cho việc tách runtime state khỏi Obsidian.

### 3. Guild Worker Prototype

Tôi xây dựng prototype Worker Team với task/artifact contract. Prototype hỗ trợ:

- tạo task
- claim task
- lease/heartbeat
- dependency unlock
- publish artifact
- join review
- generated fix task
- dashboard JSON/text

Mục tiêu của phần này là kiểm tra xem một workflow nhiều bước có thể được điều phối bằng shared blackboard thay vì chat tự do giữa các agent hay không.

### 4. Dashboard Và Worker Loop

Tôi xây dựng dashboard 4 cột theo mô hình Blackboard:

- Ready
- Claimed
- Blocked
- Done

Dashboard giúp quan sát tiến độ task, artifact, worker, và trạng thái bị block. Tôi cũng thêm fake worker và visible worker terminal để kiểm tra luồng chạy thật.

### 5. Provider Adapter

Tôi thử nghiệm provider adapter để worker có thể dùng nhiều backend khác nhau:

- local-dry-run
- local-file-writer
- opencode
- openrouter
- gemini
- groq
- auto-ammo

Tôi thêm output validation để model không thể trả output sai format mà vẫn được đánh dấu hoàn thành.

### 6. Content Factory MVP

Sau khi đánh giá lại, tôi quyết định không dùng full Guild runtime cho content factory vì nó quá phức tạp so với mục tiêu ban đầu.

MVP content factory dùng:

- n8n làm orchestrator
- Hermes/local script làm content generator
- SQLite làm queue/state
- Telegram làm human approval
- Obsidian làm style memory dài hạn

Tôi tạo CLI `scripts/content_factory.py` để:

- tạo content job
- sinh idea/script/caption
- tạo video placeholder
- gửi approval message
- lưu approve/reject

Tôi cũng cài n8n local, import workflow skeleton và xác nhận UI hoạt động.

## Kết Quả Đạt Được

Một số kết quả cụ thể:

- SQLite content job chạy được.
- Artifact files được tạo theo từng job.
- Telegram approval message gửi thành công.
- n8n server chạy được local tại `http://localhost:5678`.
- 3 workflow content factory đã import vào n8n.
- Guild runtime prototype chạy được nhiều smoke test.
- Provider output validation hoạt động.
- File scope enforcement phát hiện và chặn output ngoài allowed files.

## Khó Khăn Gặp Phải

- SQLite trong workspace `_runtime` gặp lỗi I/O/readonly trên Windows, nên phải chuyển DB bền sang AppData.
- Provider thật phụ thuộc API key, network, và sandbox.
- OpenCode prompt dài có thể gặp lỗi Windows command-line length.
- Multi-agent dễ bị overengineering nếu không giữ scope.
- n8n CLI và server có DB/port behavior riêng, cần tách user folder.
- Telegram/n8n approval callback cần cấu hình credential/webhook kỹ hơn trước khi dùng production.

## Bài Học

- Với AI workflow, state rõ ràng quan trọng hơn agent thông minh.
- Không nên để model tự do đọc/ghi toàn bộ workspace.
- Cần artifact và validation để biết task có thật sự hoàn thành hay không.
- Multi-agent chỉ nên dùng khi có lợi thật, không nên dùng cho mọi bài toán.
- n8n phù hợp cho orchestration, không phù hợp để chứa reasoning phức tạp.
- Obsidian nên là semantic memory, không phải queue.
- Local-first giúp debug tốt hơn và giảm phụ thuộc cloud.

## Hướng Phát Triển Tiếp

- Hoàn thiện n8n approval handler bằng Telegram Trigger.
- Thêm TTS thật.
- Thêm render video thật bằng template.
- Thêm trend/idea source đơn giản.
- Lưu reject reason thành style memory sau khi được distill.
- Chỉ thêm auto-post TikTok/YouTube sau khi human approval ổn định.
- Với Guild runtime, chuyển finalization từ API bridge sang worker-claimed final_review khi file-writing semantics ổn định.

