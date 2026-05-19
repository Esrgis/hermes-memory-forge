# Repo Boundaries

Hermes Memory Forge has three different layers. Keep them separate so the repo can be cloned and reused without carrying one machine's runtime state.

## 1. Public Template

This layer should be safe to publish and clone.

Examples:

- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `docs/core/HERMES_ROUTER.md`
- `docs/core/MEMORY_PIPELINE.md`
- `*.template.md`
- `templates/`
- `skills/`
- setup and scaffold scripts with clear parameters

Rules:

- Use parameters instead of hardcoded local paths.
- Provide dry-run behavior for scripts that can affect local state.
- Do not assume secrets, Telegram, cron jobs, gateway state, or one user's vault layout.
- Skills in `skills/` are repo-level procedures that future agents should read when their trigger matches, especially `dangerous-operation-guard` and `obsidian-rag-check`.

## 2. Local Runtime

This layer belongs to the current workstation and should stay ignored.

Examples:

- `_runtime/`
- `_hermes/`
- `_obsidian_vault`
- `HERMES_USER_CONFIG.md`
- `PROJECT_CONTEXT.md`
- `TASKS.md`
- `HERMES_MAP.md`
- logs, locks, SQLite files, backups, auth files, and `.env`

Rules:

- Do not commit secrets or raw chat logs.
- Do not expose private vault content.
- Distill memory before storing it in Obsidian.

## 3. Incubator

This layer contains experiments that may become public modules later.

Examples:

- blackboard CLI
- daily brief automation
- health checks
- game check-ins
- n8n/Flock integration notes
- future agent runtime and dashboard prototypes

Rules:

- Keep experiments small and reversible.
- Promote an experiment only after it has a stable command contract, dry-run mode where useful, documented failure modes, and at least one repeatable successful run.
- Do not market incubator code as a finished multi-agent framework.

## Packaging Direction

Near-term package identity:

```text
Windows-first Hermes memory workstation template
+ optional blackboard/multi-agent incubator
```

Future package identity, after runtime contracts stabilize:

```text
Hermes-based cognitive workstation with scoped multi-agent orchestration
```
