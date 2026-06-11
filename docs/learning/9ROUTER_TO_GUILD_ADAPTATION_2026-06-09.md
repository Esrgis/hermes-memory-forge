# 9Router Patterns To Adapt Into Hermes Guild

Date: 2026-06-09
Source repo: `_runtime/research/9router`
License observed: MIT, copyright 2024-2026 decolua and contributors

This note is for learning and adaptation. Do not copy substantial 9Router source into tracked Guild code without preserving the MIT notice.

## Why It Matters

9Router overlaps heavily with the provider side of Hermes Guild, but it is more mature in the router/provider UX:

- one local gateway for many tools
- provider onboarding by account/API key
- model discovery
- combo/fallback routes
- quota and usage tracking
- request logs
- skill/capability split for chat, image, TTS, STT, embeddings, web search, and web fetch

Guild should absorb these patterns so the user can run one Guild dashboard instead of running Guild, Hermes, and 9Router as separate moving parts.

## High-Value Patterns

### 1. Provider Catalog

9Router has a rich provider catalog with:

- provider id and alias
- display name, icon, color
- auth mode: OAuth, API key, cookie, no-auth
- supported service kinds such as `llm`, `embedding`, `image`, `tts`, `stt`, `webSearch`, `webFetch`
- API key URL / signup URL
- provider-specific endpoint config
- passthrough model behavior
- deprecation/risk notices

Guild action:

- Keep `config/guild/provider-transports.json` for runnable transports.
- Add a Guild-native catalog layer for UI/provider lab metadata.
- Keep keys outside tracked JSON.

First Guild artifact added:

- `config/guild/provider-capabilities.json`

### 2. Capability Skills

9Router skills are small capability entrypoints:

- `9router-chat`
- `9router-image`
- `9router-tts`
- `9router-stt`
- `9router-embeddings`
- `9router-web-search`
- `9router-web-fetch`

Each skill documents:

- endpoint
- required input fields
- model discovery route
- response shape
- provider quirks

Guild action:

- Represent these as provider capabilities, not as worker skills only.
- Map capabilities to Guild task types and allowed provider routes.
- Use capability selection before model selection.

### 3. Combos

9Router combos are named model/provider fallback chains. They appear as models and can auto-fallback.

Guild already has `ammo_ladder`, but it lacks:

- named combos
- UI reorder
- per-capability combo kind
- clear usage/quota impact

Guild action:

- Add `config/guild/provider-combos.json`.
- Treat a combo as a named ladder of cartridges.
- Preserve `capability`/`kind` so a web-search combo cannot be used as a chat model by accident.

Suggested schema:

```json
{
  "schema_version": "guild_provider_combos_v0",
  "combos": {
    "coding-stack": {
      "kind": "llm",
      "capability": "code-edit-worker",
      "items": [
        { "cartridge": "gemini:gemini-2.5-flash", "on_flags": ["provider_service_unavailable", "provider_rate_limited"] },
        { "cartridge": "groq:gpt-oss-20b", "on_flags": ["provider_service_unavailable", "provider_rate_limited"] },
        { "cartridge": "openrouter:poolside-laguna-free", "on_flags": ["provider_service_unavailable", "provider_rate_limited"] }
      ]
    }
  }
}
```

### 4. Usage And Quota

9Router tracks:

- pending requests by model/account
- usage history
- daily aggregates
- request details
- cost calculation from pricing tables
- provider/model/account/API-key breakdowns

Guild action:

- Add a small SQLite or JSONL-backed usage store under `_runtime/guild-usage/`.
- Record every adapter call from `scripts/guild_provider_adapters/invoke.py`.
- Use `provider_usage` in dashboard from this store, not only from the current payload.

Minimum event shape:

```json
{
  "schema_version": "guild_provider_usage_v0",
  "ts": "2026-06-09T00:00:00Z",
  "quest_chain_id": "quest-...",
  "task_id": "task-...",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "cartridge": "gemini:gemini-2.5-flash",
  "capability": "code-edit-worker",
  "status": "blocked",
  "blocked_reason": "provider_service_unavailable",
  "tokens": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  },
  "estimated_cost_usd": 0
}
```

### 5. Failure Flags

9Router exposes useful failure concepts such as unavailable accounts/providers and retry-after behavior. Guild already has `blocked_reason`, but it was not centralized.

Guild action already started:

- `config/guild/failure-flags.json`
- `provider_service_unavailable` and `provider_rate_limited` now retry through `auto-ammo`.

Next action:

- Load `failure-flags.json` in dashboard and show owner/category/retry policy next to blocked tasks.

### 6. Model Discovery

9Router lists models by capability route:

- `/v1/models`
- `/v1/models/image`
- `/v1/models/tts`
- `/v1/models/embedding`
- `/v1/models/web`
- `/v1/models/stt`

Guild action:

- Add a `Test Models` or `Discover Models` button in Provider Lab.
- For OpenAI-compatible transports, call `/models`.
- For static providers, use configured cartridges.
- Do not require CLI install when HTTP API exists.

### 7. Request Log Detail

9Router keeps request details separate from aggregate usage. This matches Guild's need to avoid dumping raw logs into memory.

Guild action:

- Save raw-ish provider request details under `_runtime/` only.
- Write distilled summaries into Obsidian checkpoints.
- Surface only status, provider, model, token counts, flags, and payload path in dashboard.

## Suggested Port Order

1. Keep current Guild runtime stable.
2. Wire `failure-flags.json` into dashboard blocked task rendering.
3. Add `provider-capabilities.json` to Provider Lab UI so new providers choose service kinds.
4. Add `provider-combos.json` and let `auto-ammo` resolve combo names.
5. Add `_runtime/guild-usage/provider-usage.jsonl` writes in adapter invocation.
6. Add usage/quota dashboard panel.
7. Add model discovery per provider transport.
8. Only then consider copying or vendoring specific 9Router code with MIT notice.

## What Not To Copy Yet

- Next.js dashboard structure.
- MITM/DNS tooling.
- OAuth/session providers that create account-risk surface.
- Full pricing table without current verification.
- Raw request/response logging into long-term memory.

## Immediate Guild Changes From This Pass

- Cloned 9Router into `_runtime/research/9router`.
- Added `config/guild/provider-capabilities.json`.
- Existing earlier changes in this session:
  - added `config/guild/failure-flags.json`
  - made checkpoint flush dry-run compact
  - made `provider_service_unavailable` and `provider_rate_limited` retryable in `auto-ammo`
