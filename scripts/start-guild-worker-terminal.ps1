[CmdletBinding()]
param(
    [string]$QuestChainId = "demo-even-random-app",

    [string]$Profile = "builder",

    [string]$AgentId = "builder",

    [ValidateSet("S", "A", "B", "C", "D")]
    [string]$AgentRank = "C",

    [string]$Skills = "general",

    [int]$MaxSteps = 1,

    [ValidateRange(1, 3600)]
    [int]$IntervalSeconds = 5,

    [string]$Adapter = "local-dry-run",

    [string]$Provider,

    [string]$Model,

    [switch]$UseConfiguredProvider,

    [switch]$Once,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$workerAgentScript = Join-Path $workspace "scripts\run-guild-worker-agent.ps1"
$profileScript = Join-Path $workspace "scripts\get-guild-agent-profile.ps1"

if (-not (Test-Path -LiteralPath $workerAgentScript)) {
    throw "Missing worker-agent script: $workerAgentScript"
}

if ($Profile) {
    if (-not (Test-Path -LiteralPath $profileScript)) {
        throw "Missing profile script: $profileScript"
    }
    $profileData = & $profileScript -Profile $Profile
    if (-not $profileData) {
        throw "Failed to load agent profile: $Profile"
    }
    $AgentId = $profileData.agent_id
    $AgentRank = $profileData.rank
    $Skills = $profileData.skills
}

$encodedWorkspace = $workspace.Replace("'", "''")
$encodedQuest = $QuestChainId.Replace("'", "''")
$encodedAgent = $AgentId.Replace("'", "''")
$encodedSkills = $Skills.Replace("'", "''")
$encodedProfile = $Profile.Replace("'", "''")
$encodedAdapter = $Adapter.Replace("'", "''")
$encodedProvider = if ($Provider) { $Provider.Replace("'", "''") } else { "" }
$encodedModel = if ($Model) { $Model.Replace("'", "''") } else { "" }

$tickCommand = @"
Set-Location -LiteralPath '$encodedWorkspace'
Write-Host 'Guild worker terminal: $encodedAgent / profile $encodedProfile'
Write-Host 'Quest chain: $encodedQuest'
Write-Host 'Rank/skills: $AgentRank / $encodedSkills'
Write-Host 'Adapter: $encodedAdapter'
Write-Host 'Press Ctrl+C to stop.'
`$idleCount = 0
while (`$true) {
    `$workerArgs = @{
        Profile = '$encodedProfile'
        Adapter = '$encodedAdapter'
        QuestChainId = '$encodedQuest'
        Once = `$true
        Json = `$true
    }
    if ('$encodedProvider') { `$workerArgs.Provider = '$encodedProvider' }
    if ('$encodedModel') { `$workerArgs.Model = '$encodedModel' }
    if ('$UseConfiguredProvider' -eq 'True') { `$workerArgs.UseConfiguredProvider = `$true }
    `$result = .\scripts\run-guild-worker-agent.ps1 @workerArgs
    if (`$LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host ('[{0}] worker tick failed.' -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Red
    }
    if (`$result) {
        `$parsed = `$result | ConvertFrom-Json
        if (`$parsed.claimed) {
            `$idleCount = 0
            Write-Host ''
            Write-Host ('[{0}] processing blackboard task' -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Cyan
            Write-Host ('claimed: {0}' -f `$parsed.task_id) -ForegroundColor Yellow
            Write-Host ('adapter result: ok={0} blocked={1}' -f `$parsed.adapter_result.ok, `$parsed.adapter_result.blocked_reason)
            Write-Host ('status update: {0}' -f `$parsed.status_update.status) -ForegroundColor Green
        } else {
            `$idleCount += 1
            if (`$idleCount -eq 1) {
                Write-Host ''
                Write-Host ('[{0}] idle: waiting for claimable task' -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor DarkGray
            }
        }
    }
    .\scripts\export-guild-dashboard.ps1 -QuestChainId '$encodedQuest' -IncludeArtifacts | Out-Null
    if ('$Once' -eq 'True') { break }
    Start-Sleep -Seconds $IntervalSeconds
}
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
    throw "PowerShell executable is required to launch a worker terminal."
}

if (-not $DryRun) {
    Start-Process -FilePath $pwsh.Source -ArgumentList @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", $tickCommand
    ) | Out-Null
}

[pscustomobject]@{
    launched = -not $DryRun
    dry_run = [bool]$DryRun
    profile = $Profile
    agent_id = $AgentId
    agent_rank = $AgentRank
    skills = $Skills
    adapter = $Adapter
    provider = $Provider
    model = $Model
    quest_chain_id = $QuestChainId
    interval_seconds = $IntervalSeconds
}
