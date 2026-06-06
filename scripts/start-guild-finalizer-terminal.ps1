[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$QuestChainId,

    [ValidateRange(1, 65535)]
    [int]$Port = 8765,

    [ValidateRange(1, 3600)]
    [int]$IntervalSeconds = 5,

    [ValidateRange(1, 500)]
    [int]$MaxTicks = 40,

    [ValidateRange(1, 50)]
    [int]$StableWaitingLimit = 8
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$encodedWorkspace = $workspace.Replace("'", "''")
$encodedQuest = $QuestChainId.Replace("'", "''")

$command = @"
Remove-Module PSReadLine -Force -ErrorAction SilentlyContinue
Set-Location -LiteralPath '$encodedWorkspace'
Write-Host 'Guild Hermes finalizer terminal' -ForegroundColor Magenta
Write-Host 'Quest chain: $encodedQuest'
Write-Host 'Dashboard API: http://127.0.0.1:$Port'
Write-Host 'Press Ctrl+C to stop.'
`$idleCount = 0
`$tickCount = 0
`$lastReason = ''
`$stableReasonCount = 0
while (`$true) {
    `$tickCount += 1
    try {
        `$body = @{ quest_chain_id = '$encodedQuest' } | ConvertTo-Json
        `$result = Invoke-RestMethod -Uri 'http://127.0.0.1:$Port/api/hermes/finalize' -Method Post -ContentType 'application/json' -Body `$body -TimeoutSec 20
        if (`$result.ready) {
            Write-Host ('[{0}] finalized OK' -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Green
            break
        }
        if (`$result.terminal) {
            Write-Host ('[{0}] stopping: {1}; review={2}' -f (Get-Date -Format 'HH:mm:ss'), `$result.reason, `$result.review_status) -ForegroundColor Red
            break
        }
        `$created = if (`$result.repair -and `$result.repair.created) { `$result.repair.created -join ', ' } else { 'none' }
        `$waiting = if (`$result.repair -and `$result.repair.waiting) { `$result.repair.waiting -join ', ' } else { 'none' }
        Write-Host ('[{0}] waiting: {1}; created={2}; waiting={3}' -f (Get-Date -Format 'HH:mm:ss'), `$result.reason, `$created, `$waiting) -ForegroundColor Yellow
        if (`$result.reason -eq `$lastReason) {
            `$stableReasonCount += 1
        } else {
            `$lastReason = `$result.reason
            `$stableReasonCount = 1
        }
        if (`$stableReasonCount -ge $StableWaitingLimit) {
            Write-Host ('[{0}] stopping after stable wait reason: {1}' -f (Get-Date -Format 'HH:mm:ss'), `$lastReason) -ForegroundColor Yellow
            break
        }
    } catch {
        `$idleCount += 1
        if (`$idleCount -eq 1 -or (`$idleCount % 4) -eq 0) {
            Write-Host ('[{0}] finalize tick failed: {1}' -f (Get-Date -Format 'HH:mm:ss'), `$_.Exception.Message) -ForegroundColor Red
        }
        if (`$idleCount -ge 6) {
            Write-Host ('[{0}] stopping after repeated finalize errors' -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Red
            break
        }
    }
    if (`$tickCount -ge $MaxTicks) {
        Write-Host ('[{0}] stopping after max ticks: {1}' -f (Get-Date -Format 'HH:mm:ss'), $MaxTicks) -ForegroundColor Yellow
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
}
Write-Host 'Hermes finalizer done. Leaving terminal open.' -ForegroundColor Magenta
"@

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
    throw "PowerShell executable is required to launch the Hermes finalizer terminal."
}

Start-Process -FilePath $pwsh.Source -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $command
) | Out-Null

[pscustomobject]@{
    launched = $true
    quest_chain_id = $QuestChainId
    port = $Port
}
