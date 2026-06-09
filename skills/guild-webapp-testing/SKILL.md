---
name: guild-webapp-testing
description: Use when testing the Hermes Guild Dashboard UI, plan preview, confirm run, Provider Lab, visual state, browser console behavior, or Playwright-based local webapp verification.
---

# Guild Webapp Testing

Use this skill only when the user explicitly wants UI testing or has already opened the UI.

## Default Rule

Do not start dashboard servers, open browsers, or launch visible UI without explicit user approval.

## Testing Workflow

1. Confirm the target URL and whether the server is already running.
2. If already running, use browser/HTTP checks against that URL.
3. If not running, ask before launching:

```powershell
.\scripts\open-guild-dashboard.ps1 -VisibleServer -StopExisting
```

4. For plan flow, verify:
   - `Preview Plan` creates no worker wake events.
   - `Confirm Run` creates blackboard tasks.
   - duplicate clicks are ignored while requests are in flight.
   - local smoke mode is labeled as smoke.
5. For provider flow, verify:
   - Provider Lab can list config.
   - Test Now reports blocked reasons without exposing secrets.

## Playwright Pattern

- Wait for the page to settle before inspecting DOM.
- Capture console errors.
- Prefer selectors by button text or element id.
- Close browser after scripted checks.
- Save screenshots only under `_runtime/` when needed.

## Evidence To Return

- URL tested.
- Actions performed.
- Console errors.
- Relevant event-log lines.
- Screenshot path, if captured.
- Whether UI state matched expected behavior.
