[CmdletBinding()]
param(
    [string]$QuestChainId,

    [string]$DbPath,

    [switch]$KeepDatabase
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$guild = Join-Path $workspace "scripts\guild-worker-team.py"
$worker = Join-Path $workspace "scripts\run-guild-worker-agent.ps1"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing Python runtime: $python"
}
if (-not (Test-Path -LiteralPath $guild)) {
    throw "Missing Guild worker CLI: $guild"
}
if (-not (Test-Path -LiteralPath $worker)) {
    throw "Missing worker agent script: $worker"
}

if (-not $QuestChainId) {
    $QuestChainId = "smoke-local-file-writer-{0}" -f (Get-Date -Format "yyyyMMddHHmmss")
}

$autoDbPath = $false
if (-not $DbPath) {
    $DbPath = Join-Path $env:TEMP ("hermes-{0}.sqlite" -f $QuestChainId)
    $autoDbPath = $true
}

$taskId = "$QuestChainId-build-1"
$allowedFile = "guild-workspaces/$QuestChainId/build-1.md"
$outputFile = Join-Path $workspace ("guild-workspaces\{0}\build-1.md" -f $QuestChainId)

$createArgs = @(
    $guild,
    "--db", $DbPath,
    "create-task",
    "--task-id", $taskId,
    "--task-type", "execution",
    "--required-rank", "C",
    "--required-skill", "implementation",
    "--owner-area", "smoke",
    "--status", "open",
    "--plan-review-not-required",
    "--plan-review-status", "not_required",
    "--quest-chain-id", $QuestChainId,
    "--sequence-no", "1",
    "--output-artifact", "implementation_result_1",
    "--allowed-files", $allowedFile,
    "--title", "LocalFileWriterSmoke",
    "--request", "Hermes_worker_artifact_validation_smoke",
    "--acceptance-criteria", "build1_exists",
    "--definition-of-done", "grounding_passes"
)

$createRaw = & $python @createArgs
if ($LASTEXITCODE -ne 0) {
    throw "create-task failed with exit code $LASTEXITCODE. Output: $($createRaw -join "`n")"
}

$workerResult = & $worker `
    -Profile builder `
    -Adapter local-file-writer `
    -QuestChainId $QuestChainId `
    -TaskId $taskId `
    -DbPath $DbPath `
    -MinOpenAgeSeconds 0 `
    -Json

$workerJson = $workerResult | ConvertFrom-Json

$dashboardRaw = & $python $guild --db $DbPath dashboard --quest-chain-id $QuestChainId --include-tasks --include-artifacts
if ($LASTEXITCODE -ne 0) {
    throw "dashboard read failed with exit code $LASTEXITCODE. Output: $($dashboardRaw -join "`n")"
}
$dashboard = $dashboardRaw | ConvertFrom-Json

$fileExists = Test-Path -LiteralPath $outputFile
$taskDone = ($dashboard.status_counts.done -eq 1)
$artifactPublished = ($dashboard.artifact_count -eq 1)
$groundingValid = [bool]$workerJson.artifact.payload.artifact_grounding_validation.valid

$ok = [bool]($workerJson.ok -and $taskDone -and $artifactPublished -and $fileExists -and $groundingValid)

$result = [pscustomobject]@{
    ok = $ok
    smoke = "local-file-writer"
    quest_chain_id = $QuestChainId
    db_path = $DbPath
    task_id = $taskId
    output_file = $outputFile
    file_exists = $fileExists
    task_done = $taskDone
    artifact_count = $dashboard.artifact_count
    grounding_valid = $groundingValid
    kept_database = [bool]($KeepDatabase -or -not $autoDbPath)
}

if ($autoDbPath -and -not $KeepDatabase -and (Test-Path -LiteralPath $DbPath)) {
    $resolvedDb = (Resolve-Path -LiteralPath $DbPath).Path
    $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path.TrimEnd("\")
    if ($resolvedDb.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedDb -Force
    }
}

if (-not $ok) {
    $result | ConvertTo-Json -Depth 5
    exit 1
}

$result | ConvertTo-Json -Depth 5
