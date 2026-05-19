---
name: dangerous-operation-guard
description: Use before any potentially destructive filesystem, git, workspace rename, junction/symlink, move, delete, reset, clean, cron/gateway, or memory-mutation operation. Especially important on Windows when paths may be junctions or real directories.
---

# Dangerous Operation Guard

Use this skill before executing or recommending operations that can delete, overwrite, move, rename, reset, or mutate important state.

## Trigger Examples

- `Remove-Item`, `rm`, `del`, `rmdir`, `git clean`, `git reset --hard`
- workspace rename, folder move, junction/symlink changes
- deleting or recreating `.git`
- overwriting Obsidian memory, Hermes hot memory, blackboard rows, cron/gateway config
- any command where a wrong path can remove user data

## Hard Rule

Never give or run a destructive command without first proving what the target is.

For Windows path operations, always inspect:

```powershell
Get-Item -LiteralPath 'PATH' -Force | Select-Object FullName,LinkType,Target,Attributes
```

Only remove a path that is expected to be a junction when `LinkType` is exactly `Junction`. If `LinkType` is empty and `Attributes` contains `Directory`, treat it as real data and refuse removal unless the user explicitly confirms after seeing the inspection output.

## Safe Workflow

1. State the intended target and why it is safe or unsafe.
2. Inspect the target path, parent path, and expected replacement path.
3. Check whether the current shell/agent is inside the target path.
4. Check whether `.git`, workspace files, runtime links, or vault links are inside the target.
5. Prefer rename-to-backup over delete.
6. Use dry-run or read-only inspection where available.
7. Ask for explicit approval before destructive mutation.
8. After mutation, verify the expected path, link target, git status, and key files.

## Windows Junction Rename Pattern

Do not run `Remove-Item D:\HermesGuildCore` just because that path used to be a junction. Re-check it immediately before removal.

Safe shape:

```powershell
$alias = Get-Item -LiteralPath 'D:\HermesGuildCore' -Force
if ($alias.LinkType -ne 'Junction') {
    throw "Refusing: D:\HermesGuildCore is not a junction. It is real data."
}
Remove-Item -LiteralPath 'D:\HermesGuildCore'
```

If doing a real rename:

```powershell
Get-Item -LiteralPath 'D:\TuanKeCuoi' -Force
Get-Item -LiteralPath 'D:\HermesGuildCore' -Force -ErrorAction SilentlyContinue
```

Then choose one direction and do not repeat stale commands from an earlier state.

## Recovery Preference

If damage occurs:

- stop destructive commands immediately
- inspect top-level paths first
- preserve broken remnants by moving them to a timestamped backup
- restore from GitHub only after confirming the repository was pushed
- recreate ignored local files from templates and shared memory

## Memory Guard

Investigation jobs may report findings, create suggestions, or add memory candidates. They must not delete hot memory, delete blackboard tasks, rewrite durable memory, or modify cron/gateway state without explicit user approval.
