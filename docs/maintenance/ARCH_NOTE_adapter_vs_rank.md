# ARCH NOTE: auto-rank vs auto-ammo — Đây là 2 tầng khác nhau

> Viết để Codex đọc trước khi chạm vào dashboard adapter dropdown.
> Ngày: 2026-06-10

---

## Vấn đề hiện tại

`guild-dashboard.html` dòng 1199 đang có dropdown "Adapter" với các options:

```html
<option value="auto-rank" selected>auto-rank (real workers)</option>
<option value="auto-ammo">auto-ammo</option>
<option value="opencode">opencode</option>
<option value="local-dry-run">local-dry-run (smoke only)</option>
```

**Đây là sai về kiến trúc.** `auto-rank` và `auto-ammo` không phải 2 lựa chọn thay thế nhau — chúng thuộc 2 tầng hoàn toàn khác nhau.

---

## Kiến trúc đúng

```
TẦNG 1 — CLAIM LAYER (Dashboard concern)
    auto-rank:
    - Worker profile được chọn dựa trên rank (A/B/C)
    - Worker rank C claim task rank C, rank B claim task rank B/C, v.v.
    - Chống race condition: worker rank thấp không lấy task rank cao
    - Thuộc: guild-dashboard.html + guild-dashboard-server.py
    - Quyết định: AI NÀO làm task

TẦNG 2 — EXECUTION LAYER (Adapter concern)
    auto-ammo:
    - Sau khi worker đã claim task, chọn model nào để chạy
    - Ladder: Gemini → OpenCode → Poolside (theo capability-adapters.json)
    - Nếu Gemini fail → thử OpenCode → thử Poolside
    - Thuộc: ladder.py + capability-adapters.json
    - Quyết định: MODEL NÀO chạy task
```

---

## Fix cần làm

Thay 1 dropdown bằng 2 control riêng:

```
[Worker rank policy]  auto-rank | fixed: worker-a | fixed: worker-b | fixed: worker-c
[Model selection]     auto-ammo | opencode | local-dry-run
```

Default production: `auto-rank` + `auto-ammo` — 2 cái này **không exclusive**, dùng cả 2 cùng lúc là đúng.

`guild-dashboard-server.py` dòng 541 và 605 cần được xem lại — có 2 endpoint xử lý adapter với default khác nhau (`local-dry-run` vs `opencode`). Cần đồng bộ về 1 logic.

---

## File liên quan

```
docs/incubation/guild-dashboard.html        ← dropdown cần tách thành 2
scripts/guild-dashboard-server.py           ← dòng 541, 605 cần đồng bộ
config/guild/capability-adapters.json       ← ammo ladder definition
scripts/guild_provider_adapters/ladder.py   ← auto-ammo logic
scripts/start-guild-worker-terminal.ps1     ← auto-rank được set từ profile ở đây
```

---

## Không được làm

- **Không gom auto-rank vào adapter dropdown** — rank là claim policy, không phải execution adapter
- **Không hardcode model trong dropdown** — model selection thuộc ladder config, không phải UI
- **Không xóa auto-ammo** — đây là execution layer đúng cho production, đã được patch và test

---

## Context thêm

Session 2026-06-10 đã patch:
1. `GUILD_WORKER_SYSTEM_PROMPT` constant trong `base.py` — 4 adapter dùng chung
2. `Normalize-GuildArtifactTestResult` coerce `""` → `not_required`
3. Test pass: `auto-ammo` + Gemini → `ok: true`, `artifact_validation.valid: true`

`auto-ammo` hiện tại hoạt động đúng ở execution layer. Việc còn lại là tách nó ra khỏi dropdown rank ở UI layer.
