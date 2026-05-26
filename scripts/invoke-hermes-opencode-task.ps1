[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TaskId,

    [string]$QuestChainId = "demo-opencode-handoff",

    [string]$WorkerProfile = "builder",

    [string]$WorkerAdapter = "opencode",

    [switch]$CreateIfMissing,

    [switch]$VisibleWorker,

    [switch]$NoRunWorker,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$guild = Join-Path $workspace "scripts\guild-worker-team.py"
$workerScript = Join-Path $workspace "scripts\run-guild-worker-agent.ps1"
$hermesProfile = Join-Path $workspace "scripts\get-guild-agent-profile.ps1"

function Invoke-GuildCliJson {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Arguments
    )
    $raw = & $python @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Guild CLI failed with exit code $exitCode. Output: $($raw -join "`n")"
    }
    if (-not $raw) {
        throw "Guild CLI returned no JSON output."
    }
    return ($raw | ConvertFrom-Json)
}

$hermes = & $hermesProfile -Profile hermes-codex
if (-not $hermes) {
    throw "Failed to load hermes-codex profile."
}

$inspect = Invoke-GuildCliJson -Arguments @($guild, "inspect-task", $TaskId)

if (-not $inspect.found) {
    if (-not $CreateIfMissing) {
        throw "Task '$TaskId' not found. Pass -CreateIfMissing to create a disposable execution task."
    }
    $createArgs = @(
        $guild,
        "create-task",
        "--task-id", $TaskId,
        "--task-type", "execution",
        "--required-rank", "C",
        "--required-skill", "general",
        "--owner-area", "worker_smoke",
        "--status", "blocked",
        "--plan-review-status", "approved",
        "--quest-chain-id", $QuestChainId,
        "--sequence-no", "1",
        "--output-artifact", "worker_result",
        "--title", "opencode_handoff_smoke_task",
        "--request", "return_compact_artifact_json_no_file_edits",
        "--acceptance-criteria", "artifact_published",
        "--definition-of-done", "task_done_after_artifact"
    )
    $created = Invoke-GuildCliJson -Arguments $createArgs
    $inspect = Invoke-GuildCliJson -Arguments @($guild, "inspect-task", $TaskId)
} else {
    $created = $null
}

$ready = Invoke-GuildCliJson -Arguments @($guild, "set-status", $TaskId, "open")

$worker = $null
if (-not $NoRunWorker) {
    if ($VisibleWorker) {
        $runtimeDir = Join-Path $workspace "_runtime\guild-worker-agent"
        New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
        $safeTaskId = ($TaskId -replace '[^A-Za-z0-9_.-]', '_')
        $workerRunPath = Join-Path $runtimeDir "visible-worker-$safeTaskId.ps1"
        $workerLogPath = Join-Path $runtimeDir "visible-worker-$safeTaskId.log"
        $workerResultPath = Join-Path $runtimeDir "visible-worker-$safeTaskId.result.json"
        $encodedWorkspace = $workspace.Replace("'", "''")
        $encodedTask = $TaskId.Replace("'", "''")
        $encodedQuest = $QuestChainId.Replace("'", "''")
        $encodedProfile = $WorkerProfile.Replace("'", "''")
        $encodedAdapter = $WorkerAdapter.Replace("'", "''")
        $encodedLog = $workerLogPath.Replace("'", "''")
        $encodedResult = $workerResultPath.Replace("'", "''")
        $workerScriptContent = @"
`$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '$encodedWorkspace'
Start-Transcript -LiteralPath '$encodedLog' -Force | Out-Null
try {
    Write-Host 'Hermes woke Guild worker'
    Write-Host 'Task: $encodedTask'
    Write-Host 'Quest: $encodedQuest'
    Write-Host 'Profile/adapter: $encodedProfile / $encodedAdapter'
    `$result = .\scripts\run-guild-worker-agent.ps1 -Profile '$encodedProfile' -Adapter '$encodedAdapter' -QuestChainId '$encodedQuest' -TaskId '$encodedTask' -Json
    `$result | Set-Content -LiteralPath '$encodedResult' -Encoding UTF8
    `$result
    Write-Host 'Worker finished. Press Enter to close.'
} catch {
    Write-Host "Worker failed: `$(`$_.Exception.Message)" -ForegroundColor Red
    @{ ok = `$false; error = `$_.Exception.Message } | ConvertTo-Json | Set-Content -LiteralPath '$encodedResult' -Encoding UTF8
} finally {
    Stop-Transcript | Out-Null
}
Read-Host
"@
        Set-Content -LiteralPath $workerRunPath -Value $workerScriptContent -Encoding UTF8
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
            throw "PowerShell executable is required to launch the visible worker."
        }
        Start-Process -FilePath $pwsh.Source -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $workerRunPath
        ) | Out-Null
        $worker = [pscustomobject]@{
            launched = $true
            visible = $true
            profile = $WorkerProfile
            adapter = $WorkerAdapter
            task_id = $TaskId
            quest_chain_id = $QuestChainId
            script = $workerRunPath
            log = $workerLogPath
            result = $workerResultPath
        }
    } else {
        $workerRaw = & $workerScript `
            -Profile $WorkerProfile `
            -Adapter $WorkerAdapter `
            -QuestChainId $QuestChainId `
            -TaskId $TaskId `
            -Json
        if (-not $workerRaw) {
            throw "Worker wake failed: no output."
        }
        $worker = $workerRaw | ConvertFrom-Json
    }
}

$result = [pscustomobject]@{
    ok = $true
    coordinator = "hermes-codex"
    coordinator_agent_id = $hermes.agent_id
    action = "task_ready_then_wake_worker"
    task_id = $TaskId
    quest_chain_id = $QuestChainId
    created = $created
    inspect = $inspect
    ready = $ready
    worker_profile = $WorkerProfile
    worker_adapter = $WorkerAdapter
    worker = $worker
}

if ($Json) {
    $result | ConvertTo-Json -Depth 40
} else {
    $result
}
