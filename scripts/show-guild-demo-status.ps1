[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$QuestChainId,

    [ValidateRange(1, 65535)]
    [int]$Port = 8765,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Read-TailLines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$Lines = 30
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }
    return @(Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue)
}

function Get-LocalRuntimeStatus {
    param([Parameter(Mandatory = $true)][string]$QuestChainId)

    $questDir = Join-Path $workspace "guild-workspaces\$QuestChainId"
    $questFiles = @()
    if (Test-Path -LiteralPath $questDir -PathType Container) {
        $questFiles = @(
            Get-ChildItem -LiteralPath $questDir -File |
                Sort-Object Name |
                ForEach-Object {
                    [pscustomobject]@{
                        path = (Resolve-Path -LiteralPath $_.FullName -Relative)
                        bytes = $_.Length
                        modified = $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
                    }
                }
        )
    }

    $dashboardDir = Join-Path $workspace "_runtime\dashboard"
    return [pscustomobject]@{
        quest_files = $questFiles
        guild_events_tail = Read-TailLines -Path (Join-Path $dashboardDir "guild-events.jsonl") -Lines 80
        dashboard_stderr_tail = Read-TailLines -Path (Join-Path $dashboardDir "guild-dashboard-server.err.log")
        e2e_log_tail = Read-TailLines -Path (Join-Path $dashboardDir "e2e-demo-run.log")
    }
}

$uri = "http://127.0.0.1:$Port/api/demo/status?quest_chain_id=$([uri]::EscapeDataString($QuestChainId))"
$usedFallback = $false
try {
    $status = Invoke-RestMethod -Uri $uri -TimeoutSec 5 -ErrorAction Stop
} catch {
    $usedFallback = $true
    $dashboardUri = "http://127.0.0.1:$Port/api/dashboard?quest_chain_id=$([uri]::EscapeDataString($QuestChainId))"
    $dashboardResponse = Invoke-RestMethod -Uri $dashboardUri -TimeoutSec 5 -ErrorAction Stop
    $localRuntime = Get-LocalRuntimeStatus -QuestChainId $QuestChainId
    $status = [pscustomobject]@{
        ok = [bool]$dashboardResponse.ok
        quest_chain_id = $QuestChainId
        db_path = $null
        dashboard = $dashboardResponse.dashboard
        runtime = [pscustomobject]@{
            quest_files = $localRuntime.quest_files
        }
        logs = [pscustomobject]@{
            guild_events = [pscustomobject]@{
                exists = $localRuntime.guild_events_tail.Count -gt 0
                lines = $localRuntime.guild_events_tail
            }
            dashboard_server_stderr = [pscustomobject]@{
                exists = $localRuntime.dashboard_stderr_tail.Count -gt 0
                lines = $localRuntime.dashboard_stderr_tail
            }
            e2e_demo = [pscustomobject]@{
                exists = $localRuntime.e2e_log_tail.Count -gt 0
                lines = $localRuntime.e2e_log_tail
            }
        }
        warning = "Fallback mode: /api/demo/status was not available on this server, probably because the port is running an older dashboard server process."
    }
}

if ($Json) {
    $status | ConvertTo-Json -Depth 30
    return
}

$dashboard = $status.dashboard
$summary = [ordered]@{
    ok = $status.ok
    fallback = $usedFallback
    quest_chain_id = $status.quest_chain_id
    db_path = $status.db_path
    task_count = if ($dashboard) { $dashboard.task_count } else { $null }
    artifact_count = if ($dashboard) { $dashboard.artifact_count } else { $null }
    status_counts = if ($dashboard) { ($dashboard.status_counts | ConvertTo-Json -Compress) } else { $null }
    effective_status_counts = if ($dashboard) { ($dashboard.effective_status_counts | ConvertTo-Json -Compress) } else { $null }
    repair_complete = if ($dashboard -and $dashboard.repair_summary) { $dashboard.repair_summary.complete } else { $null }
    quest_files = if ($status.runtime) { @($status.runtime.quest_files).Count } else { 0 }
}

[pscustomobject]$summary

if ($status.warning) {
    ""
    "Warning:"
    $status.warning
}

if ($status.runtime -and $status.runtime.quest_files) {
    ""
    "Quest files:"
    $status.runtime.quest_files | Select-Object path, bytes, modified | Format-Table -AutoSize
}

$events = $status.logs.guild_events
if ($events -and $events.exists -and $events.lines.Count -gt 0) {
    ""
    "Guild event log tail:"
    $events.lines | Select-Object -Last 40
}

$stderr = $status.logs.dashboard_server_stderr
if ($stderr -and $stderr.exists -and $stderr.lines.Count -gt 0) {
    ""
    "Dashboard stderr tail:"
    $stderr.lines | Select-Object -Last 30
}

$e2e = $status.logs.e2e_demo
if ($e2e -and $e2e.exists -and $e2e.lines.Count -gt 0) {
    ""
    "E2E log tail:"
    $e2e.lines | Select-Object -Last 30
}
