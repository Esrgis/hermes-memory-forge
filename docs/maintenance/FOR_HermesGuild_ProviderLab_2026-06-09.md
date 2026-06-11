# FOR: Hermes Guild Provider Lab — Session 2026-06-09

> Một ngày debug provider UI từ sáng đến tối. Đây là những gì thật sự xảy ra, tại sao, và bài học thực tế.

---

## Step 1: Approach và lý do

Hôm nay bắt đầu với mục tiêu đơn giản: làm màn hình Provider Lab hoạt động được — user nhập API key, chọn model, connect. Thế thôi.

Nhưng ngay từ đầu có 2 vấn đề song song:

1. **UI không hiển thị đúng** — field hiển thị sai, base URL không auto-fill, local vs gateway không phân biệt được
2. **Backend chưa hoàn chỉnh** — `quick_add_provider` bị 400, `list_provider_models` chỉ đọc static cartridge không gọi API thật

Approach của Claude là đi **từ symptom ngược về root cause**, không đoán mò. Mỗi lần có lỗi đều hỏi "F12 Console nói gì?" hoặc "server trả response body gì?" trước khi sửa bất cứ thứ gì.

---

## Step 2: Những hướng bị bỏ qua và tại sao

**Hướng 1: Sửa UI trước khi biết server lỗi**

Cám dỗ ban đầu là cứ nhìn UI trống mà sửa CSS/HTML. Sai — vì UI đang gọi server, server trả 400, nên dù UI có đẹp đến đâu cũng không connect được. Phải fix backend trước.

**Hướng 2: Hardcode default model cho từng provider**

Claude đề xuất thêm cerebras vào `providerDefaultModel` với model name cụ thể. Bạn bắt được ngay: "làm sao biết bên họ có những model gì nếu chưa kết nối?" — đúng hoàn toàn. Hardcode model name mà không verify là đoán mò, sẽ bị outdated ngay. Fix đúng là bỏ validate `model is required`, để user list models sau khi có key.

**Hướng 3: Copy architecture của Codex (Provider Lab)**

Codex tạo ra "Provider Lab" với form transport/cartridge/capability lộ ra ngoài cho user thấy. Đây là sai hướng — user không cần biết "transport" là gì, họ chỉ cần nhập key và chọn model. 9Router đã giải quyết đúng bài toán này rồi.

---

## Step 3: Các mảnh ghép lại với nhau như thế nào

```
provider-catalog.9router.json     ← metadata: tên, icon, auth type, signup URL
    ↓
provider-transports.json          ← runtime: base URL, env key, backend adapter
    ↓
model-cartridges.json             ← model → transport mapping
    ↓
capability-adapters.json          ← capability pool → cartridge ladder
```

Khi user click provider card:
1. `catalogProviders()` đọc catalog → render card
2. `findTransportForProvider()` match catalog entry với transport đang wired
3. `providerModalBaseUrlProfile()` quyết định base URL từ transport hoặc catalog default
4. Modal hiện đúng field theo auth type

Khi user connect:
1. `quick_add_provider` nhận payload → tạo transport entry + cartridge entry + thêm vào capability ladder
2. Secret được lưu vào `_runtime/provider-secrets.local.ps1` (file ignored bởi git)

---

## Step 4: Tools và methods

**`str_replace` / PowerShell regex replace** — dùng để apply diff trực tiếp vào file mà không cần copy paste toàn bộ file. Hiệu quả khi biết chính xác đoạn cần sửa.

**F12 Network tab** — công cụ debug quan trọng nhất. Mỗi lần bị lỗi đều xem Request payload và Response body trước khi làm bất cứ thứ gì.

**`Select-String` PowerShell** — verify fix đã vào file chưa mà không cần mở editor.

**`?v=timestamp` cache busting** — khi browser cache file HTML cũ, thêm query param là reload ngay mà không cần config server.

---

## Step 5: Tradeoffs

**Ẩn field bằng `display:none` thay vì xóa** — giữ lại JS vẫn dùng được, không phá vỡ các function đang reference element đó. Trade-off: DOM hơi thừa, nhưng safe hơn nhiều so với xóa và phải rewrite JS.

**Không implement OAuth/FreeTier ngay** — tập trung APIKey trước vì đó là cái Guild workers cần ngay. OAuth và FreeTier là nice-to-have, implement sau khi core flow hoạt động.

**Poll hotreload 1.5 giây thay vì WebSocket** — đơn giản, không cần thay đổi server. Trade-off: có độ trễ nhỏ, nhưng với file HTML tĩnh thì hoàn toàn đủ dùng.

---

## Step 6: Sai lầm và cách fix

**Sai 1: `kindPill` định nghĩa ngoài scope `.map()`**

Codex đặt 2 dòng này trước vòng lặp:
```js
const transportKind = match?.transport?.kind || "";
const kindPill = transportKind ? providerPill(transportKind) : "";
```
Nhưng `match` chỉ tồn tại *bên trong* `.map()`. Kết quả: `match` là `undefined`, `kindPill` luôn là `""`. Fix: chuyển 2 dòng đó vào trong `.map()`.

**Sai 2: Browser cache file HTML cũ**

Sửa file xong nhưng browser vẫn hiện UI cũ vì cache. Lesson: luôn thêm `?v=something` khi test, hoặc implement hotreload. Dài hạn: fix `open-guild-dashboard.ps1` để tự append timestamp vào URL.

**Sai 3: `gemini` thiếu trong `providerDefaultBaseUrl`**

Hardcode table có 15 provider nhưng thiếu gemini. URL đúng là `https://generativelanguage.googleapis.com/v1beta/openai` — đây là OpenAI compatibility layer của Google, không phải native Gemini API. Quan trọng vì Guild dùng openai-compatible adapter.

**Sai 4: Lộ API key trong chat**

Key `csk-8deky9vdjt8kc96vmpddc5t68nyerxjeycjr3kv3p9m38knt` được paste vào chat khi debug payload. Key đó đã bị lộ public, cần rotate ngay. Lesson: khi debug network request, edit phần secret trước khi paste.

**Sai 5: `findTransportForProvider` fuzzy match quá yếu**

Logic cũ dùng `haystack.includes(providerId)` — `"gemini"` match cả `gemini-api` lẫn `gemini-cli`, lấy cái đầu tiên trong object tùy thứ tự key. Fix: thêm `provider_id` field vào transport JSON, exact match trước, fuzzy match sau.

---

## Step 7: Pitfalls cần tránh

**"Model is required" validation quá sớm** — đừng validate field mà user chưa có thông tin để điền. Add provider flow: key trước → list models → chọn model → test. Không phải ngược lại.

**Codex bị ám ảnh "don't copy code"** — khi có reference implementation tốt (9Router), copy pattern là đúng, không phải xấu. Vấn đề không phải copy code mà là copy mà không hiểu. Hiểu rồi thì adapt, không cần reinvent.

**Server restart khi fix Python** — sửa `guild-dashboard-server.py` xong phải restart server. Nếu không restart thì test mãi vẫn thấy bug cũ. Dùng `open-guild-dashboard.ps1 -StopExisting` để đảm bảo.

**2 server chạy song song khác port** — Codex test trên 8765, bạn chạy trên 8781. Fix Python đúng nhưng test nhầm server, tưởng vẫn bị lỗi. Luôn kiểm tra URL đang dùng là port nào.

---

## Step 8: Điều expert nhận ra mà beginner bỏ qua

**Pattern "symptom → layer → evidence"** là cách debug đúng. Không phải nhìn UI đoán lỗi, không phải đọc code đoán behavior. Mỗi bug phải được assign về đúng 1 layer (UI / API server / adapter / config), và có evidence cụ thể (HTTP status, response body, file content) trước khi sửa.

**`kind` field trong transport JSON là metadata quan trọng** — `deterministic`, `cli`, `openai_compatible_http`, `gateway_http` không chỉ để display, mà để drive behavior: có nên gọi `/v1/models` không, có cần API key không, có phải local không. Đây là pattern từ 9Router rất đáng học.

**Catalog vs Runtime là 2 layer khác nhau** — catalog (`provider-catalog.9router.json`) là metadata để UI render, runtime (`provider-transports.json`) là config để adapter gọi. Trộn lẫn 2 layer này là nguồn gốc của nhiều bug. 9Router giữ chúng tách biệt rõ ràng.

---

## Step 9: Bài học áp dụng cho project khác

**"Auto-derive trước, manual sau"** — bất cứ khi nào system biết đủ thông tin để tự điền, đừng hỏi user. Base URL của provider đã biết → auto-fill. Env key name từ provider ID → auto-generate. Chỉ hỏi những gì system thật sự không biết (API key của user).

**Reference implementation > reinventing** — nếu có codebase đã giải quyết đúng vấn đề, đọc nó trước. 9Router đã có AddApiKeyModal, auth type branching, model fetcher hoạt động tốt. Đọc hiểu rồi port pattern, không tự nghĩ từ đầu.

**Fix validation sau khi fix flow** — validation "X is required" chỉ có ý nghĩa khi flow đã đúng. Nếu flow chưa cho user nhập X mà đã validate X → chặn user vô lý. Sequence đúng: thiết kế flow → implement → validate những gì user đã có cơ hội nhập.

**Cache là kẻ thù của development** — mọi thứ có thể bị cache: browser, process cũ, import cũ. Khi thấy behavior kỳ lạ sau khi đã fix, nghi cache trước. Hard reload, restart process, thêm timestamp vào URL.

---

## Tóm tắt ngày hôm nay

| Việc | Kết quả |
|------|---------|
| Fix `kindPill` scope bug | Done |
| Fix `gemini` missing base URL | Done |
| Fix `findTransportForProvider` exact match | Done |
| Remove `model is required` validation | Done |
| Implement `list_provider_models` gọi API thật | Done — OpenRouter 341 models, Groq 16 models |
| Modal ẩn field technical | Done |
| Auto list models sau Connect | Done |
| Model field → select dropdown | Done |
| Hotreload dev server | Done |
| Modal phân nhánh theo auth type | Prompt viết xong, Codex làm mai |

Ngày mai: Codex implement auth type branching trong modal, test end-to-end Cerebras, rồi có thể bắt đầu chạy quest thật với provider thật.
