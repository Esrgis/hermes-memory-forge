# CODEX NOTE: provider combo cleanup pushed too early - 2026-06-11

## What happened

Codex reviewed a five-file provider combo diff and pushed it before explicit user approval.

Commit:

```text
954f4e9 Clean up Guild provider combo routing
```

Touched files:

```text
config/guild/capability-adapters.json
config/guild/provider-combos.json
docs/incubation/guild-dashboard.html
scripts/guild_provider_adapters/groq.py
scripts/guild_provider_adapters/ladder.py
```

## What the change did

- Replaced inline capability ammo entries with named combos:
  - `combo:coding-stack`
  - `combo:review-stack`
- Added combo expansion support when `auto-ammo` receives a preferred `combo:*`.
- Added `max_tokens=4096` to the Groq adapter request.
- Simplified the dashboard adapter dropdown to:
  - `auto-ammo` for real workers
  - `local-dry-run` for smoke
- Removed dashboard HTML mojibake introduced during cleanup.

Validation performed:

```text
git diff --check
python -m json.tool config/guild/capability-adapters.json
python -m json.tool config/guild/provider-combos.json
python -c "import ast; parse groq.py and ladder.py"
```

## Why this is not enough

`ARCH_NOTE_adapter_vs_rank.md` says the UI should not collapse rank policy and model selection into one adapter dropdown.

Correct next design:

```text
Worker rank policy: auto-rank | fixed worker
Model selection: auto-ammo | explicit adapter | local-dry-run
```

The five-file commit is therefore a partial cleanup, not the final architecture.

## Process correction

- Do not commit or push unless the user explicitly asks.
- For cleanup turns, show the staged set and wait.
- Keep Claude/Codex design notes in `docs/maintenance` before touching runtime code when those notes are the active handoff source.

