# Guild Claude Path Map 2026-06-09

Mục tiêu của file này: đưa cho Claude một bản đồ đường đi ngắn, đủ để làm việc tiếp với Hermes Guild khi không có search nội bộ.

## 1. Đọc trước

1. `docs/learning/SYSTEM_MAP_GUILD_DEMO.md`
2. `docs/learning/GUILD_DEBUG_NAVIGATION_MAP.md`
3. `docs/learning/9ROUTER_TO_GUILD_ADAPTATION_2026-06-09.md`
4. `docs/incubation/README.md`

## 2. UI chính

- `docs/incubation/guild-dashboard.html`
- `docs/incubation/assets/provider-icons/`
- `docs/incubation/assets/provider-icons/LICENSE-9router-MIT.txt`

UI notes:
- `Board` là màn task chính.
- `Providers` là page riêng.
- Provider card mở modal.
- Click ngoài modal để đóng.
- Provider đã có metadata thì base URL nên auto-derive, không bắt người dùng gõ tay.

## 3. Dashboard API server

- `scripts/guild-dashboard-server.py`
- `scripts/open-guild-dashboard.ps1`
- `scripts/export-guild-dashboard.ps1`
- `scripts/run-guild-e2e-demo.ps1`

API route cần nhớ:
- `GET /api/health`
- `GET /api/dashboard`
- `POST /api/quest/manual`
- `POST /api/hermes/quest`
- `POST /api/wake`
- `POST /api/hermes/finalize`
- `POST /api/task/retry-blocked`
- `GET /api/provider-lab/config`
- `POST /api/provider-lab/save-secret`
- `POST /api/provider-lab/list-models`
- `POST /api/provider-lab/test`
- `POST /api/provider-lab/quick-add`
- `POST /api/provider-lab/save-combo`

## 4. Provider config

- `config/guild/provider-transports.json`
- `config/guild/model-cartridges.json`
- `config/guild/capability-adapters.json`
- `config/guild/provider-combos.json`
- `config/guild/provider-capabilities.json`
- `config/guild/failure-flags.json`
- `config/guild/provider-catalog.9router.json`

What is what:
- `provider-transports.json`: runtime transport entries that Guild actually wires.
- `model-cartridges.json`: model-to-transport entries.
- `capability-adapters.json`: capability pools and ammo ladder.
- `provider-catalog.9router.json`: imported 9Router catalog for UI and signup/key links.

## 5. Runtime provider adapters

- `scripts/guild_provider_adapters/base.py`
- `scripts/guild_provider_adapters/capabilities.py`
- `scripts/guild_provider_adapters/invoke.py`
- `scripts/guild_provider_adapters/ladder.py`
- `scripts/guild_provider_adapters/registry.py`
- `scripts/guild_provider_adapters/validation.py`
- `scripts/guild_provider_adapters/openai_compatible.py`
- `scripts/guild_provider_adapters/openrouter.py`
- `scripts/guild_provider_adapters/gemini.py`
- `scripts/guild_provider_adapters/groq.py`
- `scripts/guild_provider_adapters/opencode.py`

Wrapper:
- `scripts/invoke-guild-provider-adapter.ps1`

## 6. Worker / blackboard / workspace runtime

- `scripts/run-guild-worker-agent.ps1`
- `scripts/start-guild-worker-terminal.ps1`
- `scripts/configure-guild-worker.ps1`
- `scripts/guild-worker-team.py`
- `_runtime/flock/worker_team_prototype.py`
- `_runtime/dashboard/guild-dashboard.json`
- `_runtime/dashboard/guild-events.jsonl`
- `_runtime/session-checkpoints/`
- `_runtime/session-checkpoints/flush-preview/latest.md`

Workspace evidence:
- `guild-workspaces/<quest-id>/`

## 7. 9Router reference clone

- `_runtime/research/9router/src/shared/constants/providers.js`
- `_runtime/research/9router/src/shared/components/ProviderInfoCard.js`
- `_runtime/research/9router/src/app/(dashboard)/dashboard/providers/page.js`
- `_runtime/research/9router/src/app/(dashboard)/dashboard/providers/new/page.js`
- `_runtime/research/9router/public/providers/`
- `_runtime/research/9router/images/9router.png`

Useful 9Router ideas already mirrored into Guild:
- provider catalog separate from connected runtime
- provider cards with icon + signup/API key link
- combo/fallback concept
- quota / usage metadata
- transport view instead of one monolithic config form

## 8. If the base URL looks wrong

Read these first:

- `scripts/guild-dashboard-server.py` around `quick_add_provider`
- `docs/incubation/guild-dashboard.html` around `providerModalBaseUrlProfile`
- `docs/incubation/guild-dashboard.html` around `renderProviderModal`
- `config/guild/provider-catalog.9router.json`

Expected behavior:
- If the provider has a known catalog URL or a wired transport, the modal should auto-fill the base URL.
- If no catalog default exists, the field can stay editable.
- `quick_add_provider` should not force a manual base URL when `provider_id` already identifies a provider with a known URL.

## 9. Memory / notes

- `docs/learning/HERMES_GUILD_RUNTIME_CRASH_COURSE.md`
- `docs/learning/HANDOFF_UI_GUILD_DEMO_2026-05-22.md`
- `docs/learning/GUILD_MVP_OWNERSHIP_MAP.md`
- `docs/learning/GUILD_ARTIFACT_SCHEMA_LESSON_2026-06-05.md`
- `docs/learning/GUILD_CLAIM_RESUME_LESSON_2026-06-05.md`
- `docs/learning/GUILD_REAL_PROVIDER_ARTIFACT_ROUTE_LESSON_2026-06-05.md`

## 10. Short working rule for Claude

Start from the map above, then inspect only the smallest set of files needed for the current bug. Do not crawl the tree.
