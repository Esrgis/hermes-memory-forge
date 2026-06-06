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

    [string]$Capability,

    [string]$DbPath,

    [switch]$UseConfiguredProvider,

    [switch]$Visible,

    [switch]$Once,

    [switch]$DryRun,

    [switch]$Json
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
$encodedCapability = if ($Capability) { $Capability.Replace("'", "''") } else { "" }
$encodedDbPath = if ($DbPath) { $DbPath.Replace("'", "''") } else { "" }
$safeQuest = ($QuestChainId -replace '[^A-Za-z0-9_.-]', '-')
$safeProfile = ($Profile -replace '[^A-Za-z0-9_.-]', '-')
$questStopPath = Join-Path $workspace ("_runtime\guild-worker-agent\quest-stops\{0}.stop" -f $safeQuest)
$encodedQuestStopPath = $questStopPath.Replace("'", "''")
$sessionStamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$sessionId = "$safeQuest-$safeProfile-$sessionStamp"
$sessionRoot = Join-Path $workspace "_runtime\guild-worker-agent\terminal-sessions"
$sessionDir = Join-Path $sessionRoot $sessionId
$stdoutPath = Join-Path $sessionDir "stdout.log"
$stderrPath = Join-Path $sessionDir "stderr.log"
$metadataPath = Join-Path $sessionDir "session.json"
$loopScriptPath = Join-Path $sessionDir "worker-loop.ps1"
$hiddenRunnerPath = Join-Path $sessionDir "run-hidden.ps1"

$tickCommand = @"
Remove-Module PSReadLine -Force -ErrorAction SilentlyContinue
Set-Location -LiteralPath '$encodedWorkspace'
Write-Host 'Guild worker terminal: $encodedAgent / profile $encodedProfile'
Write-Host 'Quest chain: $encodedQuest'
Write-Host 'Rank/skills: $AgentRank / $encodedSkills'
Write-Host 'Adapter: $encodedAdapter'
if ('$encodedCapability') { Write-Host 'Capability: $encodedCapability' }
if ('$encodedProvider') { Write-Host 'Preferred ammo: $encodedProvider' }
Write-Host 'Press Ctrl+C to stop.'
`$idleCount = 0
while (`$true) {
    if (Test-Path -LiteralPath '$encodedQuestStopPath') {
        Write-Host ''
        Write-Host ('[{0}] quest stop marker found; exiting worker loop' -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Yellow
        break
    }
    `$workerArgs = @{
        Profile = '$encodedProfile'
        Adapter = '$encodedAdapter'
        QuestChainId = '$encodedQuest'
        Once = `$true
        Json = `$true
    }
    if ('$encodedProvider') { `$workerArgs.Provider = '$encodedProvider' }
    if ('$encodedModel') { `$workerArgs.Model = '$encodedModel' }
    if ('$encodedCapability') { `$workerArgs.Capability = '$encodedCapability' }
    if ('$encodedDbPath') { `$workerArgs.DbPath = '$encodedDbPath' }
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
    `$exportArgs = @{
        QuestChainId = '$encodedQuest'
        IncludeArtifacts = `$true
    }
    if ('$encodedDbPath') { `$exportArgs.DbPath = '$encodedDbPath' }
    .\scripts\export-guild-dashboard.ps1 @exportArgs | Out-Null
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

$process = $null
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
    Set-Content -LiteralPath $loopScriptPath -Value $tickCommand -Encoding UTF8
    if ($Visible) {
        $process = Start-Process -FilePath $pwsh.Source -ArgumentList @(
            "-NoExit",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $loopScriptPath
        ) -PassThru
    } else {
        $escapedLoop = $loopScriptPath.Replace("'", "''")
        $escapedStdout = $stdoutPath.Replace("'", "''")
        $hiddenRunner = @"
Set-Location -LiteralPath '$encodedWorkspace'
& '$escapedLoop' *>> '$escapedStdout'
"@
        Set-Content -LiteralPath $hiddenRunnerPath -Value $hiddenRunner -Encoding UTF8
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $pwsh.Source
        $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$hiddenRunnerPath`""
        $psi.WorkingDirectory = $workspace
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $process = [System.Diagnostics.Process]::Start($psi)
    }
}

$result = [pscustomobject]@{
    launched = -not $DryRun
    dry_run = [bool]$DryRun
    visible = [bool]$Visible
    session_id = $sessionId
    profile = $Profile
    agent_id = $AgentId
    agent_rank = $AgentRank
    skills = $Skills
    adapter = $Adapter
    provider = $Provider
    model = $Model
    capability = $Capability
    quest_chain_id = $QuestChainId
    interval_seconds = $IntervalSeconds
    process_id = if ($process) { $process.Id } else { $null }
    stdout_log = if ($DryRun -or $Visible) { $null } else { $stdoutPath }
    stderr_log = if ($DryRun -or $Visible) { $null } else { $stderrPath }
    metadata_path = if ($DryRun -or $Visible) { $null } else { $metadataPath }
    loop_script = if ($DryRun) { $null } else { $loopScriptPath }
}

if (-not $DryRun -and -not $Visible) {
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $metadataPath -Encoding UTF8
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
} else {
    $result
}
