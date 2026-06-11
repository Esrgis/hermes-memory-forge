[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",

    [int]$Port = 8765,

    [switch]$IncludeArtifacts = $true,

    [switch]$Reset,

    [switch]$NoExport,

    [switch]$NoOpen,

    [string]$DbPath,

    [switch]$VisibleServer,

    [switch]$StopExisting,

    [switch]$Enable9Router,

    [switch]$No9Router
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$htmlPath = Join-Path $workspace "docs\incubation\guild-dashboard.html"
$exportScript = Join-Path $workspace "scripts\export-guild-dashboard.ps1"
$serverScript = Join-Path $workspace "scripts\guild-dashboard-server.py"
$nineRouterScript = Join-Path $workspace "scripts\ensure-9router.ps1"
$dashboardJson = Join-Path $workspace "_runtime\dashboard\guild-dashboard.json"
$dashboardLogDir = Join-Path $workspace "_runtime\dashboard"
$serverStdoutLog = Join-Path $dashboardLogDir "guild-dashboard-server.out.log"
$serverStderrLog = Join-Path $dashboardLogDir "guild-dashboard-server.err.log"
$workerDb = if ($DbPath) { $DbPath } else { Join-Path $env:LOCALAPPDATA "hermes\flock\worker_team.sqlite" }

function Stop-ExistingGuildDashboardServers {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Workspace
    )

    $matches = @(
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -like "*guild-dashboard-server.py*" -and
                $_.CommandLine -like "*$Workspace*"
            }
    )
    foreach ($process in $matches) {
        if ($process.ProcessId -eq $PID) {
            continue
        }
        Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
    }
    return $matches.Count
}

if (-not (Test-Path -LiteralPath $htmlPath)) {
    throw "Missing dashboard HTML: $htmlPath"
}

$nineRouterStatus = $null
if ($Enable9Router -and -not $No9Router -and (Test-Path -LiteralPath $nineRouterScript)) {
    try {
        $nineRouterStatus = & $nineRouterScript
        if ($nineRouterStatus -and -not $nineRouterStatus.ok) {
            Write-Warning "9Router is not ready: $($nineRouterStatus.reason). Guild will still open; Provider Lab Test Now may be blocked."
        }
    } catch {
        Write-Warning "Could not start/check 9Router: $($_.Exception.Message)"
    }
}

if ($StopExisting) {
    New-Item -ItemType Directory -Force -Path $dashboardLogDir | Out-Null
    try {
        $stopped = Stop-ExistingGuildDashboardServers -Workspace $workspace
        $line = "[{0}] stopped {1} existing Guild dashboard server process(es)" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $stopped
        Add-Content -LiteralPath (Join-Path $dashboardLogDir "guild-events.jsonl") -Value (@{
            ts = (Get-Date).ToString("o")
            event = "dashboard_stop_existing"
            details = @{ stopped = $stopped; workspace = $workspace }
        } | ConvertTo-Json -Compress)
        Write-Host $line
    } catch {
        Write-Warning "Could not stop existing Guild dashboard servers: $($_.Exception.Message)"
    }
}

if ($Reset) {
    $python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
    $prototype = Join-Path $workspace "_runtime\flock\worker_team_prototype.py"
    & $python $prototype seed-demo-chain --quest-chain-id $QuestChainId --reset | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "seed-demo-chain failed with exit code $LASTEXITCODE"
    }
}

if (-not $NoExport) {
    $powerShellCommand = Get-Command powershell -ErrorAction SilentlyContinue
    if (-not $powerShellCommand) {
        $powerShellCommand = Get-Command pwsh -ErrorAction SilentlyContinue
    }
    if (-not $powerShellCommand) {
        $windowsPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
        if (Test-Path -LiteralPath $windowsPowerShell) {
            $powerShellCommand = [pscustomobject]@{ Source = $windowsPowerShell }
        }
    }
    if (-not $powerShellCommand) {
        throw "PowerShell executable is required to export dashboard JSON."
    }
    $exportArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $exportScript,
        "-QuestChainId", $QuestChainId
    )
    if ($IncludeArtifacts) {
        $exportArgs += "-IncludeArtifacts"
    }
    & $powerShellCommand.Source @exportArgs | Out-Null
}

if (-not (Test-Path -LiteralPath $dashboardJson)) {
    throw "Missing dashboard JSON. Run export first: $dashboardJson"
}

$serverReady = $false
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 1 -ErrorAction Stop
    $serverReady = [bool]$health.ok -and $health.db_path -eq $workerDb
} catch {
    $serverReady = $false
}

if (-not $serverReady) {
    if ($health -and $health.ok -and $health.db_path -ne $workerDb) {
        throw "Port $Port already has a stale Guild dashboard server. Use a different -Port or stop the old server. Existing db_path='$($health.db_path)', expected='$workerDb'."
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python is required to serve the static dashboard. Open manually: $htmlPath"
    }
    if (-not (Test-Path -LiteralPath $serverScript)) {
        throw "Missing Guild dashboard server: $serverScript"
    }
    New-Item -ItemType Directory -Force -Path $dashboardLogDir | Out-Null

    $args = @(
        $serverScript,
        "--workspace", "$workspace",
        "--host", "127.0.0.1",
        "--port", "$Port",
        "--db", "$workerDb"
    )
    if ($VisibleServer) {
        $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
        if (-not $pwsh) {
            $pwsh = Get-Command powershell -ErrorAction SilentlyContinue
        }
        if (-not $pwsh) {
            $windowsPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
            if (Test-Path -LiteralPath $windowsPowerShell) {
                $pwsh = [pscustomobject]@{ Source = $windowsPowerShell }
            }
        }
        if (-not $pwsh) {
            throw "PowerShell executable is required to launch a visible dashboard server."
        }
        $encodedWorkspace = $workspace.Replace("'", "''")
        $encodedPython = $python.Source.Replace("'", "''")
        $encodedServer = $serverScript.Replace("'", "''")
        $encodedDb = $workerDb.Replace("'", "''")
        $serverCommand = @"
Remove-Module PSReadLine -Force -ErrorAction SilentlyContinue
Set-Location -LiteralPath '$encodedWorkspace'
Write-Host 'Guild Dashboard server' -ForegroundColor Cyan
Write-Host 'URL: http://127.0.0.1:$Port/docs/incubation/guild-dashboard.html' -ForegroundColor Green
Write-Host 'Event log: _runtime/dashboard/guild-events.jsonl' -ForegroundColor DarkGray
Write-Host 'Press Ctrl+C to stop this server.' -ForegroundColor Yellow
& '$encodedPython' '$encodedServer' --workspace '$encodedWorkspace' --host 127.0.0.1 --port $Port --db '$encodedDb'
"@
        Start-Process -FilePath $pwsh.Source -ArgumentList @(
            "-NoExit",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command", $serverCommand
        ) | Out-Null
    } else {
        Start-Process -FilePath $python.Source -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput $serverStdoutLog -RedirectStandardError $serverStderrLog | Out-Null
    }
    Start-Sleep -Milliseconds 800
}

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$url = "http://127.0.0.1:$Port/docs/incubation/guild-dashboard.html?v=$ts"
if (-not $NoOpen) {
    Start-Process $url
}

[pscustomobject]@{
    url = $url
    html = $htmlPath
    json = $dashboardJson
    server_stdout_log = $serverStdoutLog
    server_stderr_log = $serverStderrLog
    event_log = Join-Path $dashboardLogDir "guild-events.jsonl"
    visible_server = [bool]$VisibleServer
    stopped_existing = [bool]$StopExisting
    nine_router_enabled = [bool]$Enable9Router
    nine_router = $nineRouterStatus
    quest_chain_id = $QuestChainId
    port = $Port
}
