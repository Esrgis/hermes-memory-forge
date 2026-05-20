# Agent Onboarding

Use this gate before trusting a new agent with non-trivial work in this workspace.

## Required Reading

The agent must read:

1. `START_HERE.md`
2. `AGENTS.md`
3. `docs/core/HERMES_ROUTER.md`
4. `skills/obsidian-rag-check/SKILL.md`
5. `skills/dangerous-operation-guard/SKILL.md`

## Capability Check

Before assigning work, ask the agent to answer these questions from the workspace rules:

1. What command/script is used for bounded filename or path discovery?
2. What procedure is used for memory/recall/prior-context lookup?
3. What must be read before destructive filesystem/git/path/junction/symlink operations?
4. Where should raw chat logs not be stored?
5. What should the agent do if evidence is missing or the task is too hard for the current model?

Expected answers:

1. Use `scripts/search-files.ps1`; it tries Everything ES first, then scoped `fd`, then scoped PowerShell fallback.
2. Use `skills/obsidian-rag-check/SKILL.md` and `_obsidian_vault/Specs/Memory Query Protocol Spec.md`.
3. Read `skills/dangerous-operation-guard/SKILL.md` and inspect path `LinkType`, `Target`, and `Attributes` before mutation.
4. Do not store raw chat logs in Obsidian.
5. Do not guess; search the right source tier, ask, or write a deferred-analysis note with evidence and next action.

## Trust Levels

### Level 0: Unknown

- Has not passed onboarding.
- May only answer simple questions from current context.
- No file edits.
- No broad search.
- No commands that mutate state.

### Level 1: Read-Only

- Passed capability check.
- May read bounded files and run bounded search.
- May summarize findings.
- No mutations.

### Level 2: Scoped Worker

- Passed capability check and has a specific task.
- May edit assigned files only.
- Must report changed paths.
- Must not modify runtime/gateway/cron/secrets/destructive paths.

### Level 3: Operator

- Requires explicit user approval.
- May perform higher-risk operations such as gateway/cron/provider/path-sensitive changes.
- Must use the dangerous-operation guard before destructive or path-sensitive actions.

## Task Preamble Template

Use this when assigning work to a new or weak agent:

```text
Bootstrap: read START_HERE.md and AGENTS.md first.
For memory/recall use skills/obsidian-rag-check/SKILL.md and Memory Query Protocol.
For file discovery use scripts/search-files.ps1.
Do not broad search, do not read secrets, and do not mutate files outside the assigned scope.
If evidence is missing, stop and report the missing evidence instead of guessing.
```

## Rule

Do not assume a new agent remembers the guild rules.
Make it pass the gate or keep it read-only.

