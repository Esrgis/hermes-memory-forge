---
name: guild-release-notes
description: Use when summarizing Hermes Guild changes into user-facing release notes, daily update bullets, changelogs, or checkpoint-friendly summaries from git diff, commits, and session checkpoints.
---

# Guild Release Notes

Use this skill to convert technical repo changes into concise user-facing updates.

## Workflow

1. Scope the update:
   - current dirty diff
   - since last commit
   - today
   - specific feature slice
2. Inspect bounded evidence:
   - `git status --short`
   - `git diff --stat`
   - relevant `git diff -- <paths>`
   - session checkpoint summaries when available
3. Group changes:
   - New capability
   - Behavior change
   - Fix
   - Verification
   - Known risk / not tested
4. Write in user language, not commit-message language.

## Output Shape

```markdown
## Added
- ...

## Fixed
- ...

## Verified
- ...

## Still Risky
- ...
```

## Guardrails

- Do not claim a feature is done without a verification command or runtime evidence.
- Do not include raw terminal dumps.
- Do not expose secrets.
- For internal checkpoint memory, keep it distilled and short.
