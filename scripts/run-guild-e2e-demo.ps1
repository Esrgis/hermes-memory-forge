[CmdletBinding()]
param(
    [string]$QuestChainId,

    [string]$Title = "Guild simple end-to-end demo",

    [string]$Request = "Make a one-hour Guild demo: split this prompt into requirements, risk analysis, and verification modules; each worker must write its scoped output file, then publish a final review artifact.",

    [string]$Adapter = "local-file-writer",

    [int]$Port = 8797,

    [switch]$OpenDashboard,

    [switch]$SkipProviderPreflight
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$dashboardScript = Join-Path $workspace "scripts\open-guild-dashboard.ps1"
$workerScript = Join-Path $workspace "scripts\run-guild-worker-agent.ps1"
$adapterScript = Join-Path $workspace "scripts\invoke-guild-provider-adapter.ps1"
$logPath = Join-Path $workspace "_runtime\dashboard\e2e-demo-run.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logPath) | Out-Null

function Write-DemoLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

$dbPath = Join-Path $env:TEMP "hermes-guild-e2e-demo.sqlite"
if (Test-Path -LiteralPath $dbPath) {
    Remove-Item -LiteralPath $dbPath -Force
}

if (-not $QuestChainId) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $QuestChainId = "quest-simple-e2e-$stamp"
}

if ($QuestChainId -notlike "quest-*") {
    $QuestChainId = "quest-$QuestChainId"
}

if (-not $SkipProviderPreflight -and $Adapter -notin @("local-file-writer", "local-dry-run")) {
    Write-DemoLog "Preflighting provider adapter $Adapter"
    $preflightMessage = 'Return only compact artifact JSON: {"ok":true,"summary":"provider preflight","files_changed":[],"file_outputs":[],"commands_run":[],"test_result":"not_required","known_risks":[],"blocked_reason":null}'
    $preflightRaw = & $adapterScript -Adapter $Adapter -Profile worker-a -Title "guild-e2e-provider-preflight-$Adapter" -Message $preflightMessage -Json
    if ($LASTEXITCODE -ne 0 -or -not $preflightRaw) {
        throw "Provider preflight failed to run for adapter $Adapter."
    }
    $preflight = $preflightRaw | ConvertFrom-Json
    if (-not $preflight.ok -or $preflight.blocked_reason) {
        $risk = if ($preflight.known_risks) { ($preflight.known_risks -join "`n").Substring(0, [Math]::Min(800, ($preflight.known_risks -join "`n").Length)) } else { "" }
        throw "Provider preflight failed for $Adapter`: $($preflight.summary) blocked_reason=$($preflight.blocked_reason) $risk"
    }
    Write-DemoLog "Provider preflight passed for $Adapter"
}

Write-DemoLog "Starting dashboard server on port $Port with DB $dbPath"
& $dashboardScript -Port $Port -QuestChainId $QuestChainId -DbPath $dbPath -NoExport -NoOpen | Out-Null

Write-DemoLog "Checking dashboard health"
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5
if (-not $health.ok) {
    throw "Dashboard server health check failed on port $Port."
}

$questBody = @{
    title = $Title
    request = $Request
    quest_chain_id = $QuestChainId
    allowed_files = ""
    adapter = $Adapter
} | ConvertTo-Json -Depth 8

try {
    Write-DemoLog "Creating quest $QuestChainId"
    $quest = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/quest/manual" -Method Post -ContentType "application/json" -Body $questBody -TimeoutSec 15 -ErrorAction Stop
} catch {
    $details = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    throw "Quest creation failed: $details"
}
if (-not $quest.ok) {
    throw "Quest creation failed."
}

$profiles = @("worker-a", "worker-b", "worker-c", "reviewer")
$workerResults = @()
foreach ($profile in $profiles) {
    Write-DemoLog "Running worker $profile with adapter $Adapter"
    $raw = & $workerScript -QuestChainId $QuestChainId -Profile $profile -Adapter $Adapter -DbPath $dbPath -Once -Json
    if ($LASTEXITCODE -ne 0) {
        throw "Worker $profile failed with exit code $LASTEXITCODE. Output: $($raw -join "`n")"
    }
    $workerResults += ($raw | ConvertFrom-Json)
}

$finalizeBody = @{ quest_chain_id = $QuestChainId } | ConvertTo-Json
try {
    Write-DemoLog "Finalizing quest $QuestChainId"
    $finalize = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/hermes/finalize" -Method Post -ContentType "application/json" -Body $finalizeBody -TimeoutSec 20 -ErrorAction Stop
} catch {
    $details = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    throw "Finalize failed: $details"
}
if (-not $finalize.ok -or -not $finalize.ready) {
    $repair = $finalize.repair
    $dashboardSnapshot = $finalize.dashboard
    $created = if ($repair -and $repair.created) { $repair.created -join ", " } else { "none" }
    $status = if ($dashboardSnapshot -and $dashboardSnapshot.status_counts) { ($dashboardSnapshot.status_counts | ConvertTo-Json -Compress) } else { "{}" }
    throw "Finalize not ready: reason=$($finalize.reason); status_counts=$status; repair_created=$created"
}

Write-DemoLog "Reading final dashboard"
$dashboard = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/dashboard?quest_chain_id=$([uri]::EscapeDataString($QuestChainId))" -TimeoutSec 10
if (-not $dashboard.ok) {
    throw "Dashboard read failed."
}

$questWorkspace = Join-Path $workspace "guild-workspaces\$QuestChainId"
$expectedFiles = @("build-1.md", "build-2.md", "build-3.md", "review.md", "final-summary.md", "final-artifact.json")
$fileChecks = foreach ($name in $expectedFiles) {
    $path = Join-Path $questWorkspace $name
    [pscustomobject]@{
        file = "guild-workspaces/$QuestChainId/$name"
        exists = Test-Path -LiteralPath $path -PathType Leaf
        bytes = if (Test-Path -LiteralPath $path -PathType Leaf) { (Get-Item -LiteralPath $path).Length } else { 0 }
    }
}

$failedFiles = @($fileChecks | Where-Object { -not $_.exists -or $_.bytes -le 0 })
if ($failedFiles.Count -gt 0) {
    throw "Expected output files were missing or empty: $($failedFiles.file -join ', ')"
}

Write-DemoLog "Demo complete: $QuestChainId"

$url = "http://127.0.0.1:$Port/docs/incubation/guild-dashboard.html"
if ($OpenDashboard) {
    Start-Process $url | Out-Null
}

[pscustomobject]@{
    ok = $true
    quest_chain_id = $QuestChainId
    url = $url
    db_path = $dbPath
    log_path = $logPath
    adapter = $Adapter
    task_count = $dashboard.dashboard.task_count
    artifact_count = $dashboard.dashboard.artifact_count
    status_counts = $dashboard.dashboard.status_counts
    workers = @($workerResults | ForEach-Object {
        [pscustomobject]@{
            profile = $_.profile
            claimed = $_.claimed
            task_id = $_.task_id
            status = $_.status_update.status
            blocked_reason = $_.adapter_result.blocked_reason
        }
    })
    files = $fileChecks
    final_files = $finalize.files
}
