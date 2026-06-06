[CmdletBinding()]
param(
    [string]$DbPath,

    [switch]$KeepDatabase
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$guild = Join-Path $workspace "scripts\guild-worker-team.py"
$worker = Join-Path $workspace "scripts\run-guild-worker-agent.ps1"
$adapter = Join-Path $workspace "scripts\invoke-guild-provider-adapter.ps1"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing Python runtime: $python"
}
foreach ($path in @($guild, $worker, $adapter)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing required script: $path"
    }
}

function ConvertFrom-SmokeJson {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Raw,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $text = (($Raw | ForEach-Object { [string]$_ }) -join "`n").Trim()
    $start = $text.IndexOf("{")
    if ($start -lt 0) {
        throw "$Label did not emit a JSON object. Output: $text"
    }
    $json = $text.Substring($start)
    try {
        return $json | ConvertFrom-Json
    } catch {
        throw "$Label emitted non-parseable JSON. Error: $($_.Exception.Message). Output: $text"
    }
}

$questChainId = "smoke-worker-contract-{0}" -f (Get-Date -Format "yyyyMMddHHmmss")
$autoDbPath = $false
if (-not $DbPath) {
    $DbPath = Join-Path $env:TEMP ("hermes-{0}.sqlite" -f $questChainId)
    $autoDbPath = $true
}
$scratchRoot = Join-Path $env:TEMP $questChainId
New-Item -ItemType Directory -Force -Path $scratchRoot | Out-Null

function New-SmokeTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskId,

        [Parameter(Mandatory = $true)]
        [string]$Request
    )

    $requestPath = Join-Path $scratchRoot ("{0}-request.txt" -f $TaskId)
    Set-Content -LiteralPath $requestPath -Value $Request -Encoding UTF8

    $createArgs = @(
        $guild,
        "--db", $DbPath,
        "create-task",
        "--task-id", $TaskId,
        "--task-type", "execution",
        "--required-rank", "C",
        "--required-skill", "implementation",
        "--owner-area", "smoke",
        "--status", "open",
        "--plan-review-not-required",
        "--plan-review-status", "not_required",
        "--quest-chain-id", $questChainId,
        "--sequence-no", "1",
        "--output-artifact", "worker_contract_smoke",
        "--allowed-files", "guild-workspaces/$questChainId/$TaskId.md",
        "--title", $TaskId,
        "--request-file", $requestPath,
        "--acceptance-criteria", "contract_guard_blocks_bad_output",
        "--definition-of-done", "worker_reports_clean_failure"
    )
    $createRaw = & $python @createArgs
    if ($LASTEXITCODE -ne 0) {
        throw "create-task failed for $TaskId with exit code $LASTEXITCODE. Output: $($createRaw -join "`n")"
    }
}

$invalidTaskId = "$questChainId-invalid-output"
New-SmokeTask -TaskId $invalidTaskId -Request "Return malformed adapter output so the Guild worker contract guard can block it."

$invalidWorkerRaw = & $worker `
    -Profile builder `
    -Adapter invalid-output-smoke `
    -QuestChainId $questChainId `
    -TaskId $invalidTaskId `
    -DbPath $DbPath `
    -MinOpenAgeSeconds 0 `
    -Json
if ($LASTEXITCODE -ne 0) {
    throw "invalid-output worker smoke crashed with exit code $LASTEXITCODE. Output: $($invalidWorkerRaw -join "`n")"
}
$invalidWorker = ConvertFrom-SmokeJson -Raw $invalidWorkerRaw -Label "invalid-output worker smoke"
$invalidReason = [string]$invalidWorker.artifact.payload.blocked_reason
$invalidValidation = $invalidWorker.artifact.payload.adapter_output_validation
$invalidBlockedCleanly = (-not [bool]$invalidWorker.ok) `
    -and $invalidReason -eq "invalid_adapter_output" `
    -and (-not [bool]$invalidValidation.valid)

$providerTaskId = "$questChainId-provider-exhausted"
New-SmokeTask -TaskId $providerTaskId -Request "Simulate provider exhaustion so infra failure stays retryable instead of becoming terminal failed."

$providerWorkerRaw = & $worker `
    -Profile builder `
    -Adapter provider-exhausted-smoke `
    -QuestChainId $questChainId `
    -TaskId $providerTaskId `
    -DbPath $DbPath `
    -MinOpenAgeSeconds 0 `
    -Json
if ($LASTEXITCODE -ne 0) {
    throw "provider-exhausted worker smoke crashed with exit code $LASTEXITCODE. Output: $($providerWorkerRaw -join "`n")"
}
$providerWorker = ConvertFrom-SmokeJson -Raw $providerWorkerRaw -Label "provider-exhausted worker smoke"
$providerReason = [string]$providerWorker.artifact.payload.blocked_reason

$longParts = @()
for ($i = 0; $i -lt 120; $i++) {
    $longParts += ("line {0}: verify multiline transport with quotes 'single', `"double`", braces {{}} and CLI-looking text --message should stay inside the message file." -f $i)
}
$longMessage = @"
Return only compact artifact JSON:
{"ok":true,"summary":"long message smoke","files_changed":[],"commands_run":["long-message-smoke"],"test_result":"not_required","known_risks":[],"blocked_reason":null}

$($longParts -join "`n")
"@

$longAdapterRaw = & $adapter `
    -Adapter local-dry-run `
    -Profile builder `
    -Title "guild-long-message-argv-smoke" `
    -Message $longMessage `
    -Json
if ($LASTEXITCODE -ne 0) {
    throw "long-message adapter smoke crashed with exit code $LASTEXITCODE. Output: $($longAdapterRaw -join "`n")"
}
$longAdapter = ConvertFrom-SmokeJson -Raw $longAdapterRaw -Label "long-message adapter smoke"
$longMessageOk = [bool]$longAdapter.ok -and ([string]$longAdapter.blocked_reason -eq "")

$dashboardRaw = & $python $guild --db $DbPath dashboard --quest-chain-id $questChainId --include-tasks --include-artifacts
if ($LASTEXITCODE -ne 0) {
    throw "dashboard read failed with exit code $LASTEXITCODE. Output: $($dashboardRaw -join "`n")"
}
$dashboard = ConvertFrom-SmokeJson -Raw $dashboardRaw -Label "dashboard read"
$providerTask = @($dashboard.tasks | Where-Object { $_.task_id -eq $providerTaskId }) | Select-Object -First 1
$invalidTask = @($dashboard.tasks | Where-Object { $_.task_id -eq $invalidTaskId }) | Select-Object -First 1
$providerBlockedCleanly = (-not [bool]$providerWorker.ok) `
    -and $providerReason -eq "provider_exhausted" `
    -and $providerTask `
    -and [string]$providerTask.status -eq "blocked" `
    -and [string]$providerTask.persistent_blocked_reason -eq "provider_exhausted"
$invalidFailedCleanly = $invalidTask -and [string]$invalidTask.status -eq "failed"

$retryRaw = & $python $guild --db $DbPath retry-blocked $providerTaskId
if ($LASTEXITCODE -ne 0) {
    throw "retry-blocked failed with exit code $LASTEXITCODE. Output: $($retryRaw -join "`n")"
}
$retry = ConvertFrom-SmokeJson -Raw $retryRaw -Label "retry-blocked"

$dashboardAfterRetryRaw = & $python $guild --db $DbPath dashboard --quest-chain-id $questChainId --include-tasks
if ($LASTEXITCODE -ne 0) {
    throw "dashboard after retry read failed with exit code $LASTEXITCODE. Output: $($dashboardAfterRetryRaw -join "`n")"
}
$dashboardAfterRetry = ConvertFrom-SmokeJson -Raw $dashboardAfterRetryRaw -Label "dashboard after retry read"
$providerTaskAfterRetry = @($dashboardAfterRetry.tasks | Where-Object { $_.task_id -eq $providerTaskId }) | Select-Object -First 1
$providerReopenedCleanly = [bool]$retry.reopened `
    -and [string]$retry.previous_blocked_reason -eq "provider_exhausted" `
    -and $providerTaskAfterRetry `
    -and [string]$providerTaskAfterRetry.status -eq "open" `
    -and [string]$providerTaskAfterRetry.persistent_blocked_reason -eq ""

$claimRaw = & $python $guild --db $DbPath claim-next --agent-id "retry-smoke-worker" --agent-rank "C" --skills "implementation" --task-id $providerTaskId --quest-chain-id $questChainId --min-open-age-seconds 0
if ($LASTEXITCODE -ne 0) {
    throw "claim-next after retry failed with exit code $LASTEXITCODE. Output: $($claimRaw -join "`n")"
}
$claim = ConvertFrom-SmokeJson -Raw $claimRaw -Label "claim-next after retry"
$providerClaimedAfterRetry = [bool]$claim.claimed -and [string]$claim.task.task_id -eq $providerTaskId

$ok = [bool]($invalidBlockedCleanly -and $invalidFailedCleanly -and $providerBlockedCleanly -and $providerReopenedCleanly -and $providerClaimedAfterRetry -and $longMessageOk)
$result = [pscustomobject]@{
    ok = $ok
    smoke = "worker-contract"
    quest_chain_id = $questChainId
    db_path = $DbPath
    invalid_output = [pscustomobject]@{
        task_id = $invalidTaskId
        blocked_cleanly = $invalidBlockedCleanly
        failed_cleanly = $invalidFailedCleanly
        blocked_reason = $invalidReason
        validation_errors = @($invalidValidation.errors)
    }
    provider_exhausted = [pscustomobject]@{
        task_id = $providerTaskId
        blocked_cleanly = $providerBlockedCleanly
        blocked_reason = $providerReason
        status = if ($providerTask) { $providerTask.status } else { $null }
        persistent_blocked_reason = if ($providerTask) { $providerTask.persistent_blocked_reason } else { $null }
        retry_reopened_cleanly = $providerReopenedCleanly
        retry_claimed_cleanly = $providerClaimedAfterRetry
        retry_result = $retry
    }
    long_message = [pscustomobject]@{
        ok = $longMessageOk
        adapter = $longAdapter.adapter
        message_chars = $longMessage.Length
        commands_run = @($longAdapter.commands_run)
    }
    dashboard = [pscustomobject]@{
        task_count = $dashboard.task_count
        artifact_count = $dashboard.artifact_count
        status_counts = $dashboard.status_counts
    }
    kept_database = [bool]($KeepDatabase -or -not $autoDbPath)
}

if ($autoDbPath -and -not $KeepDatabase -and (Test-Path -LiteralPath $DbPath)) {
    $resolvedDb = (Resolve-Path -LiteralPath $DbPath).Path
    $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path.TrimEnd("\")
    if ($resolvedDb.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedDb -Force
    }
}
if (-not $KeepDatabase -and (Test-Path -LiteralPath $scratchRoot -PathType Container)) {
    $resolvedScratch = (Resolve-Path -LiteralPath $scratchRoot).Path
    $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path.TrimEnd("\")
    if ($resolvedScratch.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedScratch -Recurse -Force
    }
}

$result | ConvertTo-Json -Depth 10
if (-not $ok) {
    exit 1
}
