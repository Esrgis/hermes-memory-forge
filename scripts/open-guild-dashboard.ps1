[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",

    [int]$Port = 8765,

    [switch]$IncludeArtifacts = $true,

    [switch]$Reset,

    [switch]$NoExport,

    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$htmlPath = Join-Path $workspace "docs\incubation\guild-dashboard.html"
$exportScript = Join-Path $workspace "scripts\export-guild-dashboard.ps1"
$serverScript = Join-Path $workspace "scripts\guild-dashboard-server.py"
$dashboardJson = Join-Path $workspace "_runtime\dashboard\guild-dashboard.json"
$dashboardLogDir = Join-Path $workspace "_runtime\dashboard"
$serverStdoutLog = Join-Path $dashboardLogDir "guild-dashboard-server.out.log"
$serverStderrLog = Join-Path $dashboardLogDir "guild-dashboard-server.err.log"
$workerDb = Join-Path $env:LOCALAPPDATA "hermes\flock\worker_team.sqlite"

if (-not (Test-Path -LiteralPath $htmlPath)) {
    throw "Missing dashboard HTML: $htmlPath"
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
    Start-Process -FilePath $python.Source -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput $serverStdoutLog -RedirectStandardError $serverStderrLog | Out-Null
    Start-Sleep -Milliseconds 800
}

$url = "http://127.0.0.1:$Port/docs/incubation/guild-dashboard.html"
if (-not $NoOpen) {
    Start-Process $url
}

[pscustomobject]@{
    url = $url
    html = $htmlPath
    json = $dashboardJson
    server_stdout_log = $serverStdoutLog
    server_stderr_log = $serverStderrLog
    quest_chain_id = $QuestChainId
    port = $Port
}
