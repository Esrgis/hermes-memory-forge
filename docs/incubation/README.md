# Incubation

This folder is for workflows and ideas that are not stable package surface yet.

Current incubator areas:

- blackboard runtime
- daily brief automation
- Telegram reporting
- Hermes health checks
- game check-ins
- n8n integration
- Flock or other worker orchestration
- dashboard/quest-board experiments

## Guild Dashboard UI

Open the static dashboard:

```powershell
Start-Process .\docs\incubation\guild-dashboard.html
```

Export the current Worker Team blackboard for a chain:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\export-guild-dashboard.ps1 -QuestChainId demo-even-random-app -IncludeArtifacts
```

Then load `_runtime\dashboard\guild-dashboard.json` from the page with **Load JSON**, or paste dashboard JSON directly into the textarea and click **Render Paste**.

Promotion rule:

Do not call a workflow stable until it has:

- one deterministic command or script
- clear input/output contract
- dry-run behavior when it touches external systems
- documented failure modes
- at least one successful repeat run
