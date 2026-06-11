# FOR_THANG.md — Khai Quật Smoke Temple

> Session: Debug tại sao Hermes Guild chạy nhưng OpenRouter usage = 0

---

## Step 1: Điểm xuất phát và cách tiếp cận

Bạn có một hệ thống trông như đang hoạt động — terminal hiện log, files được tạo ra, `final-artifact.json` báo `ok: true`. Nhưng trực giác nói có gì đó sai. OpenRouter usage = 0 là bằng chứng cứng nhất.

Điểm xuất phát của mình là **không tin vào bề ngoài** mà đi tìm bằng chứng từng layer:

1. API key có không?
2. HTTP request có được gửi đi không?
3. Nếu gửi đi rồi, response có được xử lý đúng không?

Cách tiếp cận là **binary search trên pipeline** — không đọc hết code mà cắt pipeline ở giữa và hỏi "đến đây thì đúng hay sai?" rồi thu hẹp dần.

---

## Step 2: Những hướng bị loại bỏ

**Hướng 1: "Model bị deprecated"** — mình kiểm tra OpenRouter models list, `poolside/laguna-m.1:free` vẫn có. Loại.

**Hướng 2: "API key sai"** — `$env:OPENROUTER_API_KEY` trả về key hợp lệ, gọi `/api/v1/models` thành công. Loại.

**Hướng 3: "Worker không claim được task"** — đây là hướng mình nghĩ đầu tiên (idle loop). Nhưng khi gọi thủ công `invoke-guild-provider-adapter.ps1` thì thấy nó trả về `local-dry-run` ngay cả khi truyền đúng provider. Hướng này đúng về symptom nhưng sai về root cause.

**Hướng 4: "System prompt thiếu schema"** — đây là hướng mình đề xuất ban đầu và bạn dừng lại đúng lúc. Bạn hỏi "có định nghĩa ở đâu đó không?" — và đúng là có, trong `WORKER_BOOTSTRAP.md` và trong `run-guild-worker-agent.ps1`. Nếu không dừng lại thì mình đã sửa sai chỗ.

Bài học: **khi bạn nghi ngờ thì đúng hơn mình**. Mình có xu hướng đề xuất fix nhanh, bạn có bản năng kiểm tra lại. Đó là thói quen tốt của một System Architect.

---

## Step 3: Các mảnh ghép kết nối với nhau như thế nào

Pipeline của Hermes Guild worker có 5 layer:

```
[Worker Loop PS1]
    → gọi run-guild-worker-agent.ps1
        → build message với GuildTask JSON đầy đủ  ← Layer 1 (chuẩn)
        → gọi invoke-guild-provider-adapter.ps1
            → gọi invoke.py
                → dispatch tới adapter cụ thể (gemini.py, openrouter.py...)
                    → system prompt ngắn + message dài  ← Layer 2 (thiếu)
                    → nhận response từ model
                → validate artifact JSON  ← Layer 3 trong Python
        → normalize + validate lại  ← Layer 3 trong PowerShell
```

Vấn đề là **Layer 2 không consistent với Layer 1**. Layer 1 đã nói rõ `test_result: "passed|failed|not_run|not_required"` nhưng Layer 2 (system prompt) chỉ nói "trả JSON đúng schema" mà không nói schema là gì. Model đọc cả 2, nhưng khi bị confuse nó ưu tiên "giải thích kết quả" hơn là "follow enum cứng".

Đây là insight quan trọng nhất của session này:

> **System prompt yếu hơn message instruction thì model ưu tiên "giải thích" hơn là follow enum.**

Nói cách khác: nếu bạn muốn model làm một việc máy móc cứng nhắc (chọn 1 trong 4 giá trị), hãy nói điều đó ở **system prompt** — nơi model coi là "tính cách" của nó — không chỉ ở user message.

---

## Step 4: Tools và methods

**`Select-String`** — grep của PowerShell, dùng để tìm pattern trong code mà không cần mở editor. Quan trọng khi codebase lớn.

**Binary search trên pipeline** — thay vì đọc hết code, gọi thẳng từng script với input giả để xem nó làm gì. Ví dụ: gọi `invoke-guild-provider-adapter.ps1 -Message "nói alo"` để test adapter độc lập với worker loop.

**Codex như codebase oracle** — khi cần biết "có file nào define X không" thì hỏi Codex nhanh hơn là grep mù. Codex có memory của toàn bộ lịch sử commit và design decision.

**`ConvertTo-Json -Depth 5`** — mặc định PowerShell chỉ serialize 3 level, nested object sẽ bị truncate. Luôn dùng `-Depth 5` khi debug JSON phức tạp.

---

## Step 5: Tradeoffs

**Patch C (coerce null → not_required):**
- Ưu: nhanh, defensive, model ngu một tý vẫn không fail
- Nhược: che giấu vấn đề — nếu model trả `null` vì nó không hiểu task thì mình đang bỏ qua signal đó

**Patch B (shared system prompt constant):**
- Ưu: một chỗ sửa, tất cả adapter đồng bộ, không còn hardcode lặp
- Nhược: chưa gom file — vẫn còn 4 file `.py` riêng, chỉ share constant thôi

**Gom thật sự (refactor về 1 base HTTP adapter):**
- Ưu: DRY hoàn toàn, fix một chỗ = fix tất cả
- Nhược: rủi ro cao hơn, cần test kỹ hơn, để sau khi hệ thống stable

Bạn chọn đúng: **làm B+C trước, gom sau**. Đây là tư duy engineering thực tế — không perfect upfront, làm stable trước rồi refactor.

---

## Step 6: Những sai lầm và dead end

**Dead end 1:** Mình đề xuất sửa system prompt ngay khi thấy nó ngắn. Bạn dừng lại và hỏi "có định nghĩa ở đâu đó không?" — đúng. Nếu không kiểm tra thì mình đã duplicate schema ở chỗ không cần thiết.

**Dead end 2:** Test với `-Message "nói alo"` — message quá đơn giản, không có GuildTask JSON, nên model trả greeting thay vì artifact. Kết quả test này không đại diện cho production behavior.

**Dead end 3:** Tưởng `qwen3-coder:free` đang chạy nhưng thực ra vẫn là `poolside` — vì cartridge config không có entry cho `qwen3-coder:free` nên fallback về default. Luôn kiểm tra `provider_summary` trong output để biết model thật nào đang chạy.

**Patch C bị miss:** Mình nghĩ patch `""` vào `Normalize-GuildArtifactTestResult` sẽ fix được `test_result: null`. Nhưng normalize đó chạy trong PowerShell, còn validation lỗi chạy trong Python (`validation.py`). Hai layer khác nhau. Fix đúng vẫn là strengthen system prompt ở Layer 2.

---

## Step 7: Bẫy cần tránh lần sau

**Bẫy 1: Tin vào output có vẻ đúng.** `build-1.md`, `build-2.md`, `build-3.md` trông rất hợp lý — đủ section, đủ nội dung. Nhưng chúng được tạo bởi `local-dry-run` với template cứng, không phải LLM. Output đẹp không có nghĩa là AI đã làm việc.

**Bẫy 2: Default adapter là `local-dry-run`.** Dòng 3 của `invoke-guild-provider-adapter.ps1`: `[string]$Adapter = "local-dry-run"`. Bất cứ lúc nào gọi adapter mà không truyền `-Adapter` rõ ràng, nó sẽ dùng dry-run. Kiểm tra default parameters trước khi debug sâu hơn.

**Bẫy 3: Model free tier không deterministic.** `poolside-laguna-free` lúc trả tool calls, lúc trả JSON, lúc trả greeting. Đừng dựa vào 1-2 lần test để kết luận model "hoạt động" hay "không hoạt động".

**Bẫy 4: Copy-paste adapter.** Khi `openrouter.py` được tạo bằng cách copy `groq.py`, fix ở `groq.py` không tự động propagate. Codebase có nhiều file gần giống nhau là dấu hiệu của technical debt — luôn grep toàn bộ khi fix một pattern.

---

## Step 8: Điều expert nhìn thấy mà beginner bỏ qua

**1. Đọc `default_adapter` trước khi đọc bất kỳ thứ gì khác.** Trong một hệ thống có nhiều adapter, default value là nơi đầu tiên cần kiểm tra khi "mọi thứ chạy nhưng không có gì xảy ra".

**2. Phân biệt validate vs normalize.** Validate là kiểm tra rồi reject. Normalize là coerce về giá trị hợp lệ. Hệ thống robust cần cả hai — normalize trước, validate sau — vì model output không bao giờ perfectly formatted.

**3. System prompt là "tính cách", user message là "nhiệm vụ".** Khi bạn muốn model làm điều gì đó một cách máy móc nhất quán (format cố định, enum cố định), đặt ở system prompt. Khi bạn muốn nói "làm việc này cụ thể", đặt ở user message. Đặt nhầm chỗ thì model sẽ "sáng tạo" ở chỗ bạn không muốn.

**4. `provider_summary` là ground truth.** Khi debug model routing, đừng tin vào tên adapter hay tên provider bạn truyền vào — đọc `provider_summary` trong output để biết model thật sự nào đã được gọi.

**5. Pipeline dài = nhiều nơi có thể fail im lặng.** Hermes Guild có ít nhất 5 layer từ worker loop đến model response. Mỗi layer có thể fail và trả về "success" giả. Debug bằng cách isolate từng layer, không đọc hết code.

---

## Step 9: Bài học áp dụng cho projects khác

**"Smoke temple" xảy ra ở mọi nơi.** Không chỉ AI systems — bất kỳ pipeline nào cũng có thể có một layer im lặng return fake success. CI/CD pipeline đôi khi "pass" vì test không được chạy. API wrapper đôi khi "return data" từ cache cũ. Luôn có một metric ground truth nằm ngoài hệ thống (như OpenRouter usage) để verify.

**Default values là technical debt ẩn.** `default="local-dry-run"` là một quyết định hợp lý khi development — không muốn tốn token khi test. Nhưng nếu production code vô tình dùng default đó thì đó là silent failure. Pattern này xuất hiện ở khắp nơi: default timeout quá dài, default retry = 0, default log level = silent.

**Shared constant > hardcode lặp, nhưng shared base class > shared constant.** B+C là bước đúng hướng. Bước tiếp theo khi có thời gian là gom 4 HTTP adapter về 1 base class — lúc đó thay đổi behavior của tất cả model calls chỉ cần sửa 1 chỗ.

**"Dù model nào đi nữa, task rank C thì trẻ lên 3 cũng làm được"** — đây là triết lý đúng. Nếu một task đủ đơn giản và đặc tả đủ rõ thì model capability không còn là biến số quan trọng nữa. Đây là cách build reliable systems với unreliable components: **make the spec so tight that there's only one way to get it right.**

---

*Viết bởi Claude sau session debug 10 June 2026.*
*"System prompt yếu hơn message instruction thì model ưu tiên giải thích hơn là follow enum."*
