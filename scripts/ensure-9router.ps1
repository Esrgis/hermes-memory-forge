[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:20128/v1",

    [int]$Port = 20128,

    [int]$ReadyTimeoutSeconds = 12,

    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runtimeDir = Join-Path $workspace "_runtime\9router"
$stdoutLog = Join-Path $runtimeDir "9router.out.log"
$stderrLog = Join-Path $runtimeDir "9router.err.log"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Test-NineRouterReady {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $modelsUrl = ($Url.TrimEnd("/") + "/models")
        $response = Invoke-RestMethod -Uri $modelsUrl -TimeoutSec 2 -ErrorAction Stop
        return [bool]$response
    } catch {
        return $false
    }
}

if (Test-NineRouterReady -Url $BaseUrl) {
    $result = [pscustomobject]@{
        ok = $true
        started = $false
        base_url = $BaseUrl
        port = $Port
        reason = "already_running"
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
    }
    if (-not $Quiet) { $result }
    return
}

$command = Get-Command 9router -ErrorAction SilentlyContinue
if (-not $command) {
    $result = [pscustomobject]@{
        ok = $false
        started = $false
        base_url = $BaseUrl
        port = $Port
        reason = "9router_not_found_on_path"
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
    }
    if (-not $Quiet) { $result }
    return
}

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
    throw "PowerShell executable is required to start 9Router in the background."
}

$encodedCommand = $command.Source.Replace("'", "''")
$serverCommand = @"
`$env:PORT = '$Port'
`$env:HOSTNAME = '127.0.0.1'
`$env:BASE_URL = 'http://127.0.0.1:$Port'
`$env:NEXT_PUBLIC_BASE_URL = 'http://127.0.0.1:$Port'
`$env:REQUIRE_API_KEY = 'false'
& '$encodedCommand'
"@

Start-Process -FilePath $pwsh.Source -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $serverCommand
) -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog | Out-Null

$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    if (Test-NineRouterReady -Url $BaseUrl) {
        $result = [pscustomobject]@{
            ok = $true
            started = $true
            base_url = $BaseUrl
            port = $Port
            reason = "started"
            stdout_log = $stdoutLog
            stderr_log = $stderrLog
        }
        if (-not $Quiet) { $result }
        return
    }
}

$result = [pscustomobject]@{
    ok = $false
    started = $true
    base_url = $BaseUrl
    port = $Port
    reason = "startup_timeout"
    stdout_log = $stdoutLog
    stderr_log = $stderrLog
}
if (-not $Quiet) { $result }
