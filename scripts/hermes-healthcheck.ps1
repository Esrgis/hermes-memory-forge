param(
    [switch]$DryRun,

    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$blackboard = Join-Path $PSScriptRoot 'blackboard.py'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "Resolve-HermesCli.ps1")

if ($DryRun) {
    $hermesCli = $null
    try {
        $hermesCli = Resolve-HermesCli -Workspace $workspace
    } catch {
        $hermesCli = $null
    }
    [pscustomobject]@{
        ok = $true
        dry_run = $true
        hermes_cli_present = [bool]$hermesCli
        hermes_cli = $hermesCli
        would_check = @(
            "hermes gateway status",
            "hermes cron list",
            "expected cron: daily-morning-brief",
            "expected cron: game-checkin-21",
            "expected cron: game-checkin-22"
        )
        would_write_blackboard_event = $true
        would_send_telegram_on_failure = $true
    }
    exit 0
}

$hermesCli = Resolve-HermesCli -Workspace $workspace
$gatewayStatus = & $hermesCli gateway status 2>&1 | Out-String
$gatewayProcessCandidates = @()
try {
    $gatewayProcessCandidates = @(Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -like '*hermes_cli.main gateway run*' -or $_.CommandLine -like '*hermes gateway run*'
    })
} catch {
    $gatewayProcessCandidates = @()
}
$gatewayProcessCandidateIds = @($gatewayProcessCandidates | ForEach-Object { $_.ProcessId })
$gatewayProcess = @(
    $gatewayProcessCandidates | Where-Object {
        $candidate = $_
        -not @($gatewayProcessCandidates | Where-Object { $_.ParentProcessId -eq $candidate.ProcessId })
    }
)
$gateway = if ($gatewayProcess) {
    "Gateway process running: $($gatewayProcess.ProcessId -join ', ')"
} else {
    $gatewayStatus
}
$cron = & $hermesCli cron list 2>&1 | Out-String

$ok = (($gatewayProcess) -or ($gatewayStatus -match 'Gateway process running')) -and ($cron -match 'daily-morning-brief') -and ($cron -match 'game-checkin-21') -and ($cron -match 'game-checkin-22')

if ($CheckOnly) {
    $gatewayCliReportsRunning = [bool]($gatewayStatus -match 'Gateway process running')
    [pscustomobject]@{
        ok = [bool]$ok
        check_only = $true
        hermes_cli = $hermesCli
        gateway_process_ids = @($gatewayProcess | ForEach-Object { $_.ProcessId })
        gateway_process_candidate_ids = $gatewayProcessCandidateIds
        gateway_status = $gateway.Trim()
        gateway_cli_status = $gatewayStatus.Trim()
        gateway_cli_reports_running = $gatewayCliReportsRunning
        gateway_status_disagrees = [bool]($gatewayProcess -and -not $gatewayCliReportsRunning)
        cron_has_daily_morning_brief = [bool]($cron -match 'daily-morning-brief')
        cron_has_game_checkin_21 = [bool]($cron -match 'game-checkin-21')
        cron_has_game_checkin_22 = [bool]($cron -match 'game-checkin-22')
    }
    if ($ok) { exit 0 } else { exit 1 }
}

if ($ok) {
    & python $blackboard event healthcheck.ok "Hermes gateway and expected cron jobs are active" | Out-Null
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

& "$PSScriptRoot\send-telegram-home.ps1" -Text $message
exit 1
