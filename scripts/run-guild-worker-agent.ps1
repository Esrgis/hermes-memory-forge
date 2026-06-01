[CmdletBinding()]
param(
    [string]$Profile = "builder",

    [string]$Adapter = "local-dry-run",

    [string]$Provider,

    [string]$Model,

    [string]$Capability,

    [string]$QuestChainId = "demo-even-random-app",

    [string]$TaskId,

    [string]$DbPath,

    [switch]$Once,

    [int]$LeaseSeconds = 900,

    [int]$ScanLimit = 50,

    [switch]$KeepClaimed,

    [switch]$UseConfiguredProvider,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $workspace "_runtime\research\flock\.venv\Scripts\python.exe"
$guild = Join-Path $workspace "scripts\guild-worker-team.py"
$profileScript = Join-Path $workspace "scripts\get-guild-agent-profile.ps1"
$adapterScript = Join-Path $workspace "scripts\invoke-guild-provider-adapter.ps1"
$providerConfigPath = Join-Path $workspace "_runtime\guild-worker-agent\provider-selection.json"
$workerBootstrapPath = Join-Path $workspace "docs\workers\WORKER_BOOTSTRAP.md"
$capabilityConfigPath = Join-Path $workspace "config\guild\capability-adapters.json"
$guildBaseArgs = @($guild)
if ($DbPath) {
    $guildBaseArgs += @("--db", $DbPath)
}

function New-GuildArgs {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Tail
    )

    $args = @()
    $args += $guildBaseArgs
    $args += $Tail
    return $args
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing Python runtime: $python"
}
if (-not (Test-Path -LiteralPath $guild)) {
    throw "Missing Guild Worker Team launcher: $guild"
}

if ($UseConfiguredProvider) {
    if (-not (Test-Path -LiteralPath $providerConfigPath)) {
        throw "Missing configured provider selection: $providerConfigPath. Run scripts\configure-guild-worker.ps1 first."
    }
    $providerConfig = Get-Content -LiteralPath $providerConfigPath -Raw | ConvertFrom-Json
    $Profile = $providerConfig.profile
    $Adapter = $providerConfig.adapter
    $Provider = $providerConfig.provider
    $Model = $providerConfig.model
    $Capability = $providerConfig.capability
}

$profileData = & $profileScript -Profile $Profile
if (-not $profileData) {
    throw "Failed to load agent profile: $Profile"
}

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

function Test-ArtifactArrayField {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    return ($null -ne $Value -and $Value -is [System.Collections.IEnumerable] -and $Value -isnot [string])
}

function Get-AllowedFilePrefixes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AllowedFiles
    )

    $prefixes = @()
    foreach ($part in ($AllowedFiles -split ',')) {
        $pattern = $part.Trim()
        if (-not $pattern) {
            continue
        }
        $normalized = $pattern -replace '\\', '/'
        $wildcardPositions = @($normalized.IndexOf('*'), $normalized.IndexOf('?')) | Where-Object { $_ -ge 0 }
        $wildcardIndex = if ($wildcardPositions.Count -gt 0) { ($wildcardPositions | Measure-Object -Minimum).Minimum } else { -1 }
        if ($wildcardIndex -ge 0) {
            $normalized = $normalized.Substring(0, $wildcardIndex)
        }
        $normalized = $normalized.TrimEnd('/')
        if ($normalized) {
            $prefixes += $normalized
        }
    }
    return $prefixes
}

function Test-DeclaredFilesWithinAllowedScope {
    param(
        [Parameter(Mandatory = $true)]
        [object]$FilesChanged,
        [Parameter(Mandatory = $true)]
        [string]$AllowedFiles
    )

    if (-not (Test-ArtifactArrayField -Value $FilesChanged)) {
        return [pscustomobject]@{
            valid = $false
            blocked_reason = "invalid_adapter_output"
            errors = @("Field files_changed must be an array.")
        }
    }

    $allowedPrefixes = @(Get-AllowedFilePrefixes -AllowedFiles $AllowedFiles)
    if ($allowedPrefixes.Count -eq 0) {
        return [pscustomobject]@{
            valid = $true
            blocked_reason = $null
            errors = @()
        }
    }

    $errors = @()
    foreach ($file in $FilesChanged) {
        $relative = [string]$file
        if ([string]::IsNullOrWhiteSpace($relative)) {
            $errors += "files_changed contains an empty path."
            continue
        }
        if ([System.IO.Path]::IsPathRooted($relative) -or $relative.Contains("..")) {
            $errors += "files_changed path is outside workspace scope: $relative"
            continue
        }
        $normalized = $relative -replace '\\', '/'
        $inScope = $false
        foreach ($prefix in $allowedPrefixes) {
            if ($normalized.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $inScope = $true
                break
            }
        }
        if (-not $inScope) {
            $errors += "files_changed path is outside allowed_files scope: $relative"
        }
    }

    return [pscustomobject]@{
        valid = ($errors.Count -eq 0)
        blocked_reason = if ($errors.Count -eq 0) { $null } else { "files_outside_allowed_scope" }
        errors = $errors
    }
}

function Get-GuildQuestWorkspacePrefix {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AllowedFiles
    )

    foreach ($part in ($AllowedFiles -split ',')) {
        $pattern = $part.Trim() -replace '\\', '/'
        if ($pattern -match '^(guild-workspaces/[^/*?]+)(?:/\*\*)?$') {
            return $Matches[1]
        }
    }
    return $null
}

function Normalize-GuildWorkerOutputPaths {
    param(
        [Parameter(Mandatory = $true)]
        [object]$WorkerOutput,
        [Parameter(Mandatory = $true)]
        [string]$AllowedFiles
    )

    $prefix = Get-GuildQuestWorkspacePrefix -AllowedFiles $AllowedFiles
    if (-not $prefix) {
        return
    }

    if (Test-ArtifactArrayField -Value $WorkerOutput.files_changed) {
        $normalizedFiles = @()
        foreach ($file in $WorkerOutput.files_changed) {
            $relative = ([string]$file) -replace '\\', '/'
            if ($relative -and -not [System.IO.Path]::IsPathRooted($relative) -and -not $relative.Contains("..") -and $relative -notmatch '/') {
                $normalizedFiles += "$prefix/$relative"
            } else {
                $normalizedFiles += $relative
            }
        }
        $WorkerOutput.files_changed = $normalizedFiles
    }

    $fields = @($WorkerOutput.PSObject.Properties.Name)
    if ($fields -contains "file_outputs" -and (Test-ArtifactArrayField -Value $WorkerOutput.file_outputs)) {
        foreach ($item in $WorkerOutput.file_outputs) {
            $itemFields = @($item.PSObject.Properties.Name)
            if ($itemFields -notcontains "path") {
                continue
            }
            $relative = ([string]$item.path) -replace '\\', '/'
            if ($relative -and -not [System.IO.Path]::IsPathRooted($relative) -and -not $relative.Contains("..") -and $relative -notmatch '/') {
                $item.path = "$prefix/$relative"
            }
        }
    }
}

function Write-GuildWorkerFileOutputs {
    param(
        [Parameter(Mandatory = $true)]
        [object]$WorkerOutput,
        [Parameter(Mandatory = $true)]
        [string]$Workspace
    )

    $written = @()
    $errors = @()
    $fieldNames = @($WorkerOutput.PSObject.Properties.Name)
    if ($fieldNames -notcontains "file_outputs" -or $null -eq $WorkerOutput.file_outputs) {
        return [pscustomobject]@{
            ok = $true
            skipped = $true
            written = @()
            errors = @()
        }
    }
    if (-not (Test-ArtifactArrayField -Value $WorkerOutput.file_outputs)) {
        return [pscustomobject]@{
            ok = $false
            skipped = $false
            written = @()
            errors = @("Optional file_outputs must be an array when present.")
        }
    }

    foreach ($item in $WorkerOutput.file_outputs) {
        $itemFields = @($item.PSObject.Properties.Name)
        if ($itemFields -notcontains "path" -or $itemFields -notcontains "content") {
            $errors += "Each file_outputs item must include path and content."
            continue
        }
        $relative = [string]$item.path
        if ([string]::IsNullOrWhiteSpace($relative) -or [System.IO.Path]::IsPathRooted($relative) -or $relative.Contains("..")) {
            $errors += "Refusing unsafe file_outputs path: $relative"
            continue
        }
        $target = Join-Path $Workspace $relative
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Set-Content -LiteralPath $target -Value ([string]$item.content) -Encoding UTF8
        $written += ($relative -replace '\\', '/')
    }

    return [pscustomobject]@{
        ok = ($errors.Count -eq 0)
        skipped = $false
        written = $written
        errors = $errors
    }
}

function ConvertFrom-GuildArtifactJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    $candidate = $Text.Trim()
    if ($candidate -match '(?s)^```(?:json)?\s*(.*?)\s*```$') {
        $candidate = $Matches[1].Trim()
    }
    if ($candidate -notmatch '^\s*\{') {
        $start = $candidate.IndexOf('{')
        $end = $candidate.LastIndexOf('}')
        if ($start -ge 0 -and $end -gt $start) {
            $candidate = $candidate.Substring($start, $end - $start + 1)
        }
    }
    return $candidate | ConvertFrom-Json
}

function Test-GuildArtifactOutput {
    param(
        [Parameter(Mandatory = $true)]
        [object]$AdapterResult
    )

    $requiredFields = @(
        "ok",
        "summary",
        "files_changed",
        "commands_run",
        "test_result",
        "known_risks",
        "blocked_reason"
    )
    $errors = @()
    $output = $null

    if (-not $AdapterResult.ok) {
        return [pscustomobject]@{
            valid = $false
            skipped = $true
            blocked_reason = if ($AdapterResult.blocked_reason) { $AdapterResult.blocked_reason } else { "adapter_failed" }
            errors = @("Adapter did not report ok=true.")
            output = $null
        }
    }

    if ($AdapterResult.blocked_reason) {
        return [pscustomobject]@{
            valid = $false
            skipped = $true
            blocked_reason = $AdapterResult.blocked_reason
            errors = @("Adapter reported blocked_reason.")
            output = $null
        }
    }

    if ([string]::IsNullOrWhiteSpace([string]$AdapterResult.text)) {
        return [pscustomobject]@{
            valid = $false
            skipped = $false
            blocked_reason = "invalid_adapter_output"
            errors = @("Adapter text is empty; expected artifact JSON.")
            output = $null
        }
    }

    try {
        $output = ConvertFrom-GuildArtifactJson -Text ([string]$AdapterResult.text)
    } catch {
        return [pscustomobject]@{
            valid = $false
            skipped = $false
            blocked_reason = "invalid_adapter_output"
            errors = @("Adapter text is not valid JSON: $($_.Exception.Message)")
            output = $null
        }
    }

    $fieldNames = @($output.PSObject.Properties.Name)
    foreach ($field in $requiredFields) {
        if ($fieldNames -notcontains $field) {
            $errors += "Missing required artifact field: $field"
        }
    }

    if ($fieldNames -contains "ok" -and $output.ok -isnot [bool]) {
        $errors += "Field ok must be boolean."
    }
    if ($fieldNames -contains "summary" -and [string]::IsNullOrWhiteSpace([string]$output.summary)) {
        $errors += "Field summary must be a non-empty string."
    }
    foreach ($arrayField in @("files_changed", "commands_run", "known_risks")) {
        if ($fieldNames -contains $arrayField -and -not (Test-ArtifactArrayField -Value $output.$arrayField)) {
            $errors += "Field $arrayField must be an array."
        }
    }
    if ($fieldNames -contains "test_result") {
        $allowedTestResults = @("passed", "failed", "not_run", "not_required")
        if ($allowedTestResults -notcontains ([string]$output.test_result)) {
            $errors += "Field test_result must be one of: $($allowedTestResults -join ', ')."
        }
    }
    if ($fieldNames -contains "blocked_reason" -and $null -ne $output.blocked_reason -and $output.blocked_reason -isnot [string]) {
        $errors += "Field blocked_reason must be null or string."
    }

    if ($errors.Count -gt 0) {
        return [pscustomobject]@{
            valid = $false
            skipped = $false
            blocked_reason = "invalid_adapter_output"
            errors = $errors
            output = $output
        }
    }

    return [pscustomobject]@{
        valid = $true
        skipped = $false
        blocked_reason = $null
        errors = @()
        output = $output
    }
}

$claimArgs = New-GuildArgs -Tail @(
    "claim-next",
    "--agent-id", $profileData.agent_id,
    "--agent-rank", $profileData.rank,
    "--skills", $profileData.skills,
    "--lease-seconds", $LeaseSeconds,
    "--scan-limit", $ScanLimit
)
if ($TaskId) {
    $claimArgs += @("--task-id", $TaskId)
}
if ($QuestChainId) {
    $claimArgs += @("--quest-chain-id", $QuestChainId)
}

$claim = Invoke-GuildCliJson -Arguments $claimArgs
if (-not $claim.claimed) {
    $result = [pscustomobject]@{
        ok = $true
        claimed = $false
        profile = $Profile
        adapter = $Adapter
        provider = $Provider
        model = $Model
        agent_id = $profileData.agent_id
        task_id = $TaskId
        quest_chain_id = $QuestChainId
        reason = "no_claimable_task"
        claim = $claim
    }
    if ($Json) { $result | ConvertTo-Json -Depth 20 } else { $result }
    return
}

$task = $claim.task
$taskJson = $task | ConvertTo-Json -Depth 20
$visibleScope = if ($task.task_type -eq "join_review") { "join_review" } else { "task_only" }
$mayCreateFixTask = if ($task.task_type -eq "join_review") { "true" } else { "false" }
$bootstrapHint = if (Test-Path -LiteralPath $workerBootstrapPath) {
    "docs/workers/WORKER_BOOTSTRAP.md"
} else {
    "missing; obey task contract and allowed_files"
}
$capabilityHint = if (Test-Path -LiteralPath $capabilityConfigPath) {
    "config/guild/capability-adapters.json"
} else {
    "missing; use task allowed_files as the authority"
}
$message = @"
NON-INTERACTIVE EXECUTION: a Guild task has already been assigned to you.
Do not ask for another task. Do not wait for more input.
Produce the final worker artifact JSON now.

You are a HermesGuildCore Guild worker.

Agent profile:
- id: $($profileData.agent_id)
- rank: $($profileData.rank)
- skills: $($profileData.skills)

Bootstrap reference: $bootstrapHint
Capability policy reference: $capabilityHint

Context envelope:
{
  "visible_scope": "$visibleScope",
  "hidden_board": true,
  "may_create_fix_task": $mayCreateFixTask,
  "must_publish_artifact": true
}

Scope rules:
- For visible_scope=task_only, use only this task packet and its explicit dependency context.
- Do not infer or inspect unrelated company/project tasks.
- Do not read secrets.
- Do not edit outside allowed_files.
- If another task appears incompatible, do not silently absorb a contract mismatch; return blocked_reason.
- Tiny compatibility adjustments are acceptable only inside this task's allowed_files and must be reported in the artifact summary.
- For visible_scope=join_review, compare upstream artifacts and report integration mismatches; propose a bounded fix task instead of broad repair.

Current GuildTask JSON:
$taskJson

Return only compact artifact JSON with this shape:
{
  "ok": true,
  "summary": "short result",
  "files_changed": [],
  "file_outputs": [
    {"path": "relative/path/inside/allowed_files.md", "content": "file text to write"}
  ],
  "commands_run": [],
  "test_result": "passed|failed|not_run|not_required",
  "known_risks": [],
  "blocked_reason": null
}

If the task asks you to write a deliverable file and you are not directly editing the filesystem,
put that file path in files_changed and include the exact file text in file_outputs.
"@

$adapterArgs = @{
    Adapter = $Adapter
    Profile = $Profile
    Title = "guild-agent-$($profileData.agent_id)-$($task.task_id)"
    Message = $message
    Json = $true
}
if ($Provider) {
    $adapterArgs.Provider = $Provider
}
if ($Model) {
    $adapterArgs.Model = $Model
}
if ($Capability) {
    $adapterArgs.Capability = $Capability
}
if ($task.task_type) {
    $adapterArgs.TaskType = [string]$task.task_type
}
$adapterRaw = & $adapterScript @adapterArgs
if (-not $adapterRaw) {
    throw "Provider adapter failed with exit code $LASTEXITCODE"
}
$adapterResult = $adapterRaw | ConvertFrom-Json

$artifactValidation = Test-GuildArtifactOutput -AdapterResult $adapterResult
$workerOutput = $artifactValidation.output
if ($workerOutput) {
    Normalize-GuildWorkerOutputPaths -WorkerOutput $workerOutput -AllowedFiles ([string]$task.allowed_files)
}
$scopeValidation = if ($workerOutput) {
    Test-DeclaredFilesWithinAllowedScope -FilesChanged $workerOutput.files_changed -AllowedFiles ([string]$task.allowed_files)
} else {
    [pscustomobject]@{
        valid = $false
        blocked_reason = "invalid_adapter_output"
        errors = @("Adapter output did not produce a worker payload.")
    }
}
$fileWrite = if ($workerOutput -and [bool]$artifactValidation.valid -and [bool]$scopeValidation.valid) {
    Write-GuildWorkerFileOutputs -WorkerOutput $workerOutput -Workspace $workspace
} else {
    [pscustomobject]@{
        ok = $false
        skipped = $true
        written = @()
        errors = @("Skipped file output write because artifact or scope validation failed.")
    }
}
$artifactOk = [bool]$adapterResult.ok `
    -and -not $adapterResult.blocked_reason `
    -and [bool]$artifactValidation.valid `
    -and [bool]$scopeValidation.valid `
    -and [bool]$fileWrite.ok `
    -and [bool]$workerOutput.ok `
    -and -not $workerOutput.blocked_reason

$effectiveBlockedReason = if ($adapterResult.blocked_reason) {
    $adapterResult.blocked_reason
} elseif (-not $artifactValidation.valid) {
    $artifactValidation.blocked_reason
} elseif ($scopeValidation -and -not $scopeValidation.valid) {
    $scopeValidation.blocked_reason
} elseif ($fileWrite -and -not $fileWrite.ok) {
    "file_output_write_failed"
} elseif ($workerOutput -and $workerOutput.blocked_reason) {
    $workerOutput.blocked_reason
} else {
    $null
}

$artifactPayload = [ordered]@{
    ok = $artifactOk
    mode = "guild_worker_agent_v0"
    task_id = $task.task_id
    task_type = $task.task_type
    quest_chain_id = $task.quest_chain_id
    producer_agent_id = $profileData.agent_id
    profile = $Profile
    adapter = $Adapter
    provider = $Provider
    model = $Model
    adapter_result = $adapterResult
    adapter_output_validation = $artifactValidation
    file_scope_validation = $scopeValidation
    file_output_write = $fileWrite
    worker_output = $workerOutput
    blocked_reason = $effectiveBlockedReason
}
$payloadJson = $artifactPayload | ConvertTo-Json -Depth 30 -Compress
$humanSummary = if ($artifactOk) {
    if ($workerOutput -and $workerOutput.summary) {
        [string]$workerOutput.summary
    } else {
        "Agent $($profileData.agent_id) produced adapter artifact for $($task.title)"
    }
} else {
    "Agent $($profileData.agent_id) blocked or failed on $($task.title): $effectiveBlockedReason"
}
$artifactPayload["summary"] = $humanSummary
$payloadJson = $artifactPayload | ConvertTo-Json -Depth 30 -Compress
$summary = if ($artifactOk) {
    "agent_$($profileData.agent_id)_completed_$($task.task_id)"
} else {
    "agent_$($profileData.agent_id)_failed_$($task.task_id)"
}
$payloadDir = Join-Path $workspace "_runtime\guild-worker-agent"
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null
$payloadPath = Join-Path $payloadDir "$($task.task_id)-$($profileData.agent_id)-payload.json"
Set-Content -LiteralPath $payloadPath -Value $payloadJson -Encoding UTF8

$publish = Invoke-GuildCliJson -Arguments (New-GuildArgs -Tail @(
    "publish-artifact",
    "--task-id", $task.task_id,
    "--artifact-type", $task.output_artifact,
    "--producer-agent-id", $profileData.agent_id,
    "--summary", $summary,
    "--payload-json-file", $payloadPath
))

$statusUpdate = $null
if ($artifactOk -and -not $KeepClaimed) {
    $statusUpdate = Invoke-GuildCliJson -Arguments (New-GuildArgs -Tail @("set-status", $task.task_id, "done"))
} elseif (-not $artifactOk -and -not $KeepClaimed) {
    if ($effectiveBlockedReason -eq "needs_info") {
        $statusUpdate = Invoke-GuildCliJson -Arguments (New-GuildArgs -Tail @(
            "set-status",
            $task.task_id,
            "blocked",
            "--blocked-reason",
            $effectiveBlockedReason
        ))
    } else {
        $statusUpdate = Invoke-GuildCliJson -Arguments (New-GuildArgs -Tail @("set-status", $task.task_id, "failed"))
    }
}

$unlock = Invoke-GuildCliJson -Arguments (New-GuildArgs -Tail @("unlock-ready", "--limit", "50"))

$result = [pscustomobject]@{
    ok = $artifactOk
    claimed = $true
    profile = $Profile
    adapter = $Adapter
    provider = $Provider
    model = $Model
    agent_id = $profileData.agent_id
    task_id = $task.task_id
    task_title = $task.title
    artifact = $publish
    status_update = $statusUpdate
    unlock = $unlock
    adapter_result = $adapterResult
}

if ($Json) {
    $result | ConvertTo-Json -Depth 30
} else {
    $result
}
