# Loose Notes

Ghi chú rời rạc để nhớ khi viết báo cáo.

## Những Câu Có Thể Dùng

- Dự án không bắt đầu từ việc "làm chatbot", mà từ nhu cầu có một assistant nhớ được việc đã làm và biết gọi đúng công cụ.
- Memory không phải lưu tất cả. Memory là nén ngữ nghĩa.
- Blackboard hữu ích vì agent có thể trao đổi qua trạng thái và artifact, không cần chat qua lại vô tận.
- Human approval là guardrail quan trọng trước khi hệ thống làm hành động public như đăng video.
- n8n nên là người bấm nút, Hermes nên là người suy nghĩ.

## Những Thứ Nghe To Nhưng Thật Ra Là Prototype

- Guild runtime
- Worker Team
- S-rank Hermes
- Provider Lab
- auto-ammo
- join_review

Khi viết báo cáo nên giải thích là các tên này dùng như metaphor/architecture prototype, không phải sản phẩm production.

## Những Thứ Có Evidence Tốt

- `TASKS.md` có timeline rất dài.
- Daily notes 2026-05-18, 19, 20, 21, 22, 26.
- `scripts/content_factory.py` là artifact mới nhất cho content factory.
- `docs/content-factory/MVP.md` là spec rõ nhất cho hướng n8n + Hermes + SQLite.
- n8n local đã cài ở `_runtime/n8n-runner`, nhưng runtime install không nên commit.

## Những Thứ Cần Nói Cẩn Thận

- Không nói hệ thống đã autonomous hoàn chỉnh.
- Không nói đã auto-post TikTok/YouTube.
- Không nói n8n approval handler đã production-ready.
- Không lộ API keys/provider secrets.
- Không đưa raw chat logs vào phụ lục.
- Không gọi đây là "AI company"; gọi là workflow/agent orchestration prototype.

## Thành Phần Có Thể Vẽ Sơ Đồ

Sơ đồ memory:

```text
Conversation
-> Distillation
-> Obsidian Daily / Shared Memory
-> FTS Search
-> Context Injection
```

Sơ đồ Guild:

```text
User Request
-> Hermes Plan
-> SQLite Task Queue
-> Worker Claim
-> Artifact Publish
-> Join Review
-> Fix / Final Summary
```

Sơ đồ Content Factory:

```text
n8n Schedule
-> Create SQLite Job
-> Generate Script/Caption
-> Render Placeholder/Video
-> Telegram Approval
-> SQLite Decision
```

## Bài Học Cá Nhân

- Đừng xây multi-agent trước khi có queue và artifact rõ ràng.
- Đừng dùng Obsidian làm database runtime.
- Đừng gọi provider thật trước khi deterministic smoke pass.
- Đừng để model trả text tự do rồi coi là done.
- Mọi workflow public-facing nên có human gate.
- Debug trên Windows cần chú ý PATH, PowerShell executable, SQLite location, command-line length.

## Trạng Thái Gần Nhất

- n8n server đã từng start OK trên `http://localhost:5678`.
- Health/readiness OK.
- 3 workflow content factory đã import vào n8n local DB.
- Content factory Telegram approval gửi thật được message id `74`.
- Job `job-telegram-20260527` đang ở trạng thái `approval_pending` tại thời điểm test.

