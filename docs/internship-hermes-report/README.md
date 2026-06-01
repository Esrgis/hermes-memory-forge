# Hermes Internship Report Pack

Folder này gom lại những thứ đã làm/test trong dự án HermesGuildCore để dùng khi viết báo cáo thực tập.

Nó không phải tài liệu sản phẩm hoàn chỉnh. Nó là bộ ghi nhớ thực dụng: có cái đã chạy thật, có cái là prototype, có cái là ý tưởng bị cắt bớt vì quá phức tạp.

## Cách Dùng

Đọc theo thứ tự:

0. `00-raw-dump/` - bãi xả rác để nhét ghi chú cũ/thô cho Codex đọc lại.
1. `01-timeline.md` - mốc thời gian theo ngày.
2. `02-tested-work.md` - những thứ đã test/làm được.
3. `03-architecture-summary.md` - kiến trúc hiện tại, boundary, phần thật/chưa thật.
4. `04-internship-report-draft.md` - bản nháp có thể đưa vào báo cáo.
5. `05-loose-notes.md` - ghi chú rời rạc/nhảm nhưng có ích khi nhớ lại.

## Phạm Vi

Dự án xoay quanh:

- Hermes local assistant
- Obsidian semantic memory
- SQLite blackboard/runtime state
- Guild/multi-agent worker prototype
- Dashboard điều phối task/artifact
- Provider adapter experiments
- n8n workflow direction
- Content factory MVP cho TikTok/Shorts approval pipeline

## Nguyên Tắc Khi Viết Báo Cáo

- Nói rõ đây là local-first assistant/workflow prototype, không phải production SaaS.
- Phân biệt phần đã chạy với phần mới là kiến trúc/ý tưởng.
- Không nói quá mức "autonomous multi-agent hoàn chỉnh".
- Nhấn mạnh quá trình thử-sai, smoke test, guardrail, và human approval.
- Không đưa secret/API key/path nhạy cảm vào báo cáo.
