param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$blackboard = Join-Path $PSScriptRoot 'blackboard.py'

$gatewayStatus = hermes gateway status 2>&1 | Out-String
$gatewayProcess = @()
try {
    $gatewayProcess = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -like '*hermes_cli.main gateway run*' -or $_.CommandLine -like '*hermes gateway run*'
    }
} catch {
    $gatewayProcess = @()
}
$gateway = if ($gatewayProcess) {
    "Gateway process running: $($gatewayProcess.ProcessId -join ', ')"
} else {
    $gatewayStatus
}
$cron = hermes cron list 2>&1 | Out-String

$ok = (($gatewayProcess) -or ($gatewayStatus -match 'Gateway process running')) -and ($cron -match 'daily-morning-brief') -and ($cron -match 'game-checkin-21') -and ($cron -match 'game-checkin-22')

if ($ok) {
    & python $blackboard event healthcheck.ok "Hermes gateway and expected cron jobs are active" | Out-Null
    if ($DryRun) { "OK" }
    exit 0
}

& python $blackboard event healthcheck.fail "Hermes healthcheck failed" | Out-Null
$message = @(
    "Hermes healthcheck canh bao.",
    "",
    "Gateway:",
    $gateway.Trim(),
    "",
    "Cron:",
    $cron.Trim()
) -join "`n"

if ($DryRun) {
    $message
    exit 1
}

& "$PSScriptRoot\send-telegram-home.ps1" -Text $message
exit 1
