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

    [int]$MinOpenAgeSeconds = -1,

    [switch]$KeepClaimed,

    [switch]$UseConfiguredProvider,

    [switch]$ArtifactValidationSelfTest,

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
$guildRuntimeConfigPath = Join-Path $workspace "config\guild\guild-runtime.json"
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

function Test-GuildQuestStopRequested {
    param([string]$QuestId)

    if ([string]::IsNullOrWhiteSpace($QuestId)) {
        return $false
    }
    $safeQuestId = ($QuestId -replace '[^A-Za-z0-9_.-]', '-')
    $stopPath = Join-Path $workspace ("_runtime\guild-worker-agent\quest-stops\{0}.stop" -f $safeQuestId)
    return (Test-Path -LiteralPath $stopPath -PathType Leaf)
}

function Test-RetryableInfrastructureBlockedReason {
    param([string]$Reason)

    $retryableReasons = @(
        "adapter_not_implemented",
        "provider_auth_failed",
        "provider_error_event",
        "provider_failed",
        "provider_missing",
        "provider_rate_limited",
        "provider_service_unavailable",
        "provider_timeout",
        "provider_exhausted"
    )
    return $retryableReasons -contains ([string]$Reason)
}

function Add-GuildEventLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Event,
        [Parameter(Mandatory = $true)]
        [hashtable]$Details
    )

    try {
        $logDir = Join-Path $workspace "_runtime\dashboard"
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
        $record = [ordered]@{
            ts = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
            event = $Event
            details = $Details
        }
        $line = $record | ConvertTo-Json -Depth 12 -Compress
        Add-Content -LiteralPath (Join-Path $logDir "guild-events.jsonl") -Value $line -Encoding UTF8
    } catch {
        # Logging must never break worker execution.
    }
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

if ($MinOpenAgeSeconds -lt 0) {
    $MinOpenAgeSeconds = 0
    if (Test-Path -LiteralPath $guildRuntimeConfigPath) {
        $runtimeConfig = Get-Content -LiteralPath $guildRuntimeConfigPath -Raw | ConvertFrom-Json
        if ($runtimeConfig.scheduler -and $null -ne $runtimeConfig.scheduler.claim_cooldown_seconds) {
            $MinOpenAgeSeconds = [int]$runtimeConfig.scheduler.claim_cooldown_seconds
        }
    }
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
        [object]$FilesChanged,
        [Parameter(Mandatory = $true)]
        [string]$AllowedFiles
    )

    if ($null -eq $FilesChanged) {
        $FilesChanged = @()
    }

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

function Test-GuildFileOutputsWithinAllowedScope {
    param(
        [Parameter(Mandatory = $true)]
        [object]$WorkerOutput,
        [Parameter(Mandatory = $true)]
        [string]$AllowedFiles
    )

    $fieldNames = @($WorkerOutput.PSObject.Properties.Name)
    if ($fieldNames -notcontains "file_outputs" -or $null -eq $WorkerOutput.file_outputs) {
        return [pscustomobject]@{
            valid = $true
            blocked_reason = $null
            errors = @()
        }
    }

    if (-not (Test-ArtifactArrayField -Value $WorkerOutput.file_outputs)) {
        return [pscustomobject]@{
            valid = $false
            blocked_reason = "invalid_adapter_output"
            errors = @("file_outputs must be an array.")
        }
    }

    $errors = @()
    $paths = @()
    foreach ($item in $WorkerOutput.file_outputs) {
        $itemFields = @($item.PSObject.Properties.Name)
        if ($itemFields -notcontains "path") {
            $errors += "Each file_outputs item must include path."
            continue
        }
        $relative = ([string]$item.path).Trim() -replace '\\', '/'
        if ([string]::IsNullOrWhiteSpace($relative)) {
            $errors += "file_outputs contains an empty path."
            continue
        }
        if ([System.IO.Path]::IsPathRooted($relative) -or $relative.Contains("..")) {
            $errors += "file_outputs path is outside workspace scope: $relative"
            continue
        }
        $paths += $relative
    }

    if ($errors.Count -gt 0) {
        return [pscustomobject]@{
            valid = $false
            blocked_reason = "files_outside_allowed_scope"
            errors = $errors
        }
    }

    if ($paths.Count -eq 0) {
        return [pscustomobject]@{
            valid = $true
            blocked_reason = $null
            errors = @()
        }
    }

    return Test-DeclaredFilesWithinAllowedScope -FilesChanged $paths -AllowedFiles $AllowedFiles
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

function New-GuildGroundingPacket {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Task
    )

    $request = ([string]$Task.request).ToLowerInvariant()
    $title = ([string]$Task.title).ToLowerInvariant()
    $skill = ([string]$Task.required_skill).ToLowerInvariant()
    $combined = "$title`n$request`n$skill"
    $allowedFiles = [string]$Task.allowed_files
    $questPrefix = Get-GuildQuestWorkspacePrefix -AllowedFiles $allowedFiles
    $lines = @(
        "Grounding packet:",
        "- Workspace root: D:\HermesGuildCore",
        "- Allowed output scope: $allowedFiles",
        "- Quest workspace prefix: $(if ($questPrefix) { $questPrefix } else { 'use allowed_files only' })",
        "- Task output artifact: $($Task.output_artifact)",
        "- Use only facts in this packet, the Current GuildTask JSON, and visible upstream context."
    )

    if ($combined.Contains("retry provider block") -or $combined.Contains("retry-provider-block") -or $combined.Contains("provider") -or $combined.Contains("route") -or $combined.Contains("config")) {
        $lines += @(
            "",
            "Known HermesGuildCore provider/retry facts:",
            "- Real retry route: POST /api/task/retry-blocked",
            "- Retry route behavior: reopens one retryable provider-blocked task to open/Ready and does not wake workers.",
            "- Dashboard data route: GET /api/dashboard?quest_chain_id=<quest-chain-id>",
            "- Real dashboard UI file: docs/incubation/guild-dashboard.html",
            "- Real dashboard backend file: scripts/guild-dashboard-server.py",
            "- Real scheduler file: _runtime/flock/worker_team_prototype.py",
            "- Real worker runner file: scripts/run-guild-worker-agent.ps1",
            "- Real planner skill config: config/guild/planner-skills.json",
            "- Real capability ladder config: config/guild/capability-adapters.json",
            "- Real provider adapter config: config/guild/provider-adapters.json",
            "- Real artifact validation module: scripts/guild_provider_adapters/validation.py",
            "- Retryable provider blocked reasons: provider_exhausted, provider_failed, provider_timeout, provider_missing, provider_error_event, adapter_not_implemented.",
            "- Non-provider schema/grounding failures such as invalid_adapter_output and ungrounded_artifact_output are not provider retry cases."
        )
    }

    if ($combined.Contains("smoke") -or $combined.Contains("verification") -or $combined.Contains("verify")) {
        $lines += @(
            "",
            "Known bounded verification commands:",
            "- python .\scripts\test-guild-artifact-validation-smoke.py",
            "- .\scripts\test-guild-worker-contract-smoke.ps1",
            "- .\scripts\test-guild-local-file-writer-smoke.ps1",
            "- git diff --check"
        )
    }

    $lines += @(
        "",
        "Forbidden hallucinations:",
        "- Do not invent src/frontend, src/backend, /dashboard/retry-provider-block, /api/providers/retry-block, /api/v1/providers/{provider_id}/block/retry, enable_blocked_provider_retry, task_execution_adapter, ProviderBlockRetryButton.js, provider_service.py, or application.yaml.",
        "- If a route, file, command, or config key is not listed in this packet or upstream context, label it unknown instead of inventing it.",
        "- The deliverable must cite exact HermesGuildCore paths/routes above when discussing Retry provider block."
    )
    return ($lines -join "`n")
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
            $missing = @()
            if ($itemFields -notcontains "path") { $missing += "path" }
            if ($itemFields -notcontains "content") { $missing += "content" }
            $hint = if ($itemFields -contains "summary" -and $itemFields -notcontains "content") { " (got 'summary' instead of 'content' -- file_outputs[].content must be the full file text, not a description)" } else { "" }
            $errors += "file_outputs item missing required field(s): $($missing -join ', ')$hint"
            continue
        }
        $relative = [string]$item.path
        if ([string]::IsNullOrWhiteSpace($relative) -or [System.IO.Path]::IsPathRooted($relative) -or $relative.Contains("..")) {
            $errors += "Refusing unsafe file_outputs path: $relative"
            continue
        }
        $target = Join-Path $Workspace $relative
        $content = [string]$item.content
        if ($content.ToLowerInvariant().Contains("see file written directly to disk")) {
            if (Test-Path -LiteralPath $target -PathType Leaf) {
                $existing = Get-Content -LiteralPath $target -Raw
                if ($existing.Trim().Length -ge 400 -and -not $existing.ToLowerInvariant().Contains("see file written directly to disk")) {
                    $written += ($relative -replace '\\', '/')
                    continue
                }
            }
            $errors += "Refusing placeholder file_outputs content without durable file on disk: $relative"
            continue
        }
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Set-Content -LiteralPath $target -Value $content -Encoding UTF8
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

function Normalize-GuildArtifactStringList {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }
    if (Test-ArtifactArrayField -Value $Value) {
        $items = @()
        foreach ($item in $Value) {
            $text = [string]$item
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                $items += $text.Trim()
            }
        }
        return $items
    }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return @()
    }
    return @($text.Trim())
}

function Normalize-GuildArtifactTestResult {
    param([object]$Value)

    $text = ([string]$Value).Trim().ToLowerInvariant()
    switch ($text) {
        "pass" { return "passed" }
        "passed" { return "passed" }
        "fail" { return "failed" }
        "failed" { return "failed" }
        "skip" { return "not_run" }
        "skipped" { return "not_run" }
        "notrun" { return "not_run" }
        "not_run" { return "not_run" }
        "notrequired" { return "not_required" }
        "not_required" { return "not_required" }
        "not-needed" { return "not_required" }
        "not_needed" { return "not_required" }
        "not applicable" { return "not_required" }
        "n/a" { return "not_required" }
        "" { return "not_required" }
        default { return $Value }
    }
}

function Normalize-GuildArtifactOutput {
    param([Parameter(Mandatory = $true)] [object]$Output)

    $fieldNames = @($Output.PSObject.Properties.Name)
    if (($fieldNames -contains "ok") -and [bool]$Output.ok) {
        if ($fieldNames -notcontains "blocked_reason") {
            $Output | Add-Member -NotePropertyName "blocked_reason" -NotePropertyValue $null
            $fieldNames = @($Output.PSObject.Properties.Name)
        } elseif ($Output.blocked_reason -is [string] -and [string]::IsNullOrWhiteSpace([string]$Output.blocked_reason)) {
            $Output.blocked_reason = $null
        }
    }
    foreach ($arrayField in @("files_changed", "commands_run", "known_risks")) {
        if ($fieldNames -contains $arrayField) {
            $Output.$arrayField = @(Normalize-GuildArtifactStringList -Value $Output.$arrayField)
        }
    }
    if ($fieldNames -contains "file_outputs") {
        if ($null -eq $Output.file_outputs) {
            $Output.file_outputs = @()
        } elseif ($Output.file_outputs -isnot [System.Collections.IEnumerable] -or $Output.file_outputs -is [string] -or $Output.file_outputs.PSObject.Properties.Name -contains "path") {
            $Output.file_outputs = @($Output.file_outputs)
        }
    }
    if ($fieldNames -contains "test_result") {
        $Output.test_result = Normalize-GuildArtifactTestResult -Value $Output.test_result
    }
    return $Output
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

    $adapterFieldNames = @($AdapterResult.PSObject.Properties.Name)
    if ($adapterFieldNames -contains "artifact_validation" -and $null -ne $AdapterResult.artifact_validation) {
        $artifactValidation = $AdapterResult.artifact_validation
        $validationNames = @($artifactValidation.PSObject.Properties.Name)
        if (($validationNames -contains "valid") -and [bool]$artifactValidation.valid -and ($validationNames -contains "output") -and $null -ne $artifactValidation.output) {
            $output = Normalize-GuildArtifactOutput -Output $artifactValidation.output
        }
    }

    if ($null -eq $output) {
        try {
            $output = Normalize-GuildArtifactOutput -Output (ConvertFrom-GuildArtifactJson -Text ([string]$AdapterResult.text)
)
        } catch {
            return [pscustomobject]@{
                valid = $false
                skipped = $false
                blocked_reason = "invalid_adapter_output"
                errors = @("Adapter text is not valid JSON: $($_.Exception.Message)")
                output = $null
            }
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
    if ($fieldNames -contains "file_outputs" -and -not (Test-ArtifactArrayField -Value $output.file_outputs)) {
        $errors += "Optional file_outputs must be an array when present."
    }
    if ($fieldNames -contains "test_result") {
        $allowedTestResults = @("passed", "failed", "not_run", "not_required")
        if ($allowedTestResults -notcontains ([string]$output.test_result)) {
            $errors += "Field test_result must be one of: $($allowedTestResults -join ', ')."
        }
    }
    if ($fieldNames -contains "blocked_reason") {
        if ($null -ne $output.blocked_reason -and $output.blocked_reason -isnot [string]) {
            $errors += "Field blocked_reason must be null or string."
        }
        if ($output.blocked_reason -is [string] -and [string]::IsNullOrWhiteSpace([string]$output.blocked_reason)) {
            $errors += "Field blocked_reason must be null or a non-empty string."
        }
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

function Get-GuildWorkerOutputText {
    param(
        [Parameter(Mandatory = $true)]
        [object]$WorkerOutput,
        [string]$Workspace
    )

    $parts = @()
    foreach ($field in @("summary", "blocked_reason")) {
        $names = @($WorkerOutput.PSObject.Properties.Name)
        if ($names -contains $field -and $null -ne $WorkerOutput.$field) {
            $parts += [string]$WorkerOutput.$field
        }
    }
    $names = @($WorkerOutput.PSObject.Properties.Name)
    if ($names -contains "file_outputs" -and (Test-ArtifactArrayField -Value $WorkerOutput.file_outputs)) {
        foreach ($item in $WorkerOutput.file_outputs) {
            $itemNames = @($item.PSObject.Properties.Name)
            if ($itemNames -contains "path") {
                $parts += [string]$item.path
            }
            if ($itemNames -contains "content") {
                $parts += [string]$item.content
            }
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($Workspace) -and $names -contains "files_changed" -and (Test-ArtifactArrayField -Value $WorkerOutput.files_changed)) {
        $workspaceRoot = (Resolve-Path -LiteralPath $Workspace).Path
        foreach ($relativePath in $WorkerOutput.files_changed) {
            $relative = ([string]$relativePath).Trim()
            if (-not $relative -or [System.IO.Path]::IsPathRooted($relative) -or $relative.Contains("..")) {
                continue
            }
            $fullPath = Join-Path $workspaceRoot $relative
            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
                continue
            }
            $resolved = (Resolve-Path -LiteralPath $fullPath).Path
            if (-not $resolved.StartsWith($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                continue
            }
            $parts += (Get-Content -LiteralPath $resolved -Raw -ErrorAction SilentlyContinue)
        }
    }
    return ($parts -join "`n")
}

function Get-GuildReviewContext {
    param([Parameter(Mandatory = $true)] [object]$Task)

    if ([string]$Task.task_type -ne "join_review") {
        return "No upstream review context required for this task."
    }
    $questId = [string]$Task.quest_chain_id
    if ([string]::IsNullOrWhiteSpace($questId) -or $questId.Contains("..")) {
        return "No safe quest workspace context available."
    }
    $questWorkspace = Join-Path $workspace ("guild-workspaces\{0}" -f $questId)
    if (-not (Test-Path -LiteralPath $questWorkspace -PathType Container)) {
        return "Quest workspace not found: guild-workspaces/$questId"
    }

    $files = @(Get-ChildItem -LiteralPath $questWorkspace -File -Filter "*.md" |
        Where-Object { $_.Name -notin @("review.md", "final-summary.md") } |
        Sort-Object @{ Expression = { if ($_.Name -eq "task-brief.md") { 0 } else { 1 } } }, Name)
    if ($files.Count -eq 0) {
        return "No upstream Markdown files found in guild-workspaces/$questId"
    }

    $parts = @()
    foreach ($file in $files) {
        $content = Get-Content -LiteralPath $file.FullName -Raw
        if ($content.Length -gt 6000) {
            $content = $content.Substring(0, 6000) + "`n[truncated]"
        }
        $parts += "## $($file.Name)`n$content"
    }
    return ($parts -join "`n`n")
}

function Invoke-GuildArtifactValidationSelfTest {
    $baseArtifact = [ordered]@{
        ok = $true
        summary = "smoke artifact validation"
        files_changed = @()
        commands_run = @()
        test_result = "not_required"
        known_risks = @()
    }
    $missingResult = Test-GuildArtifactOutput -AdapterResult ([pscustomobject]@{
        ok = $true
        blocked_reason = $null
        text = ($baseArtifact | ConvertTo-Json -Depth 10 -Compress)
    })
    $artifactWithNull = [ordered]@{}
    foreach ($key in $baseArtifact.Keys) { $artifactWithNull[$key] = $baseArtifact[$key] }
    $artifactWithNull["blocked_reason"] = $null
    $nullResult = Test-GuildArtifactOutput -AdapterResult ([pscustomobject]@{
        ok = $true
        blocked_reason = $null
        text = ($artifactWithNull | ConvertTo-Json -Depth 10 -Compress)
    })
    $nearValidArtifact = [ordered]@{
        ok = $true
        summary = "smoke artifact alias normalization"
        files_changed = "guild-workspaces/demo/build-1.md"
        commands_run = "smoke command"
        test_result = "pass"
        known_risks = "minor formatting drift"
        blocked_reason = " "
        file_outputs = [ordered]@{
            path = "guild-workspaces/demo/build-1.md"
            content = "smoke content"
        }
    }
    $nearValidResult = Test-GuildArtifactOutput -AdapterResult ([pscustomobject]@{
        ok = $true
        blocked_reason = $null
        text = ($nearValidArtifact | ConvertTo-Json -Depth 10 -Compress)
    })
    return [pscustomobject]@{
        ok = ([bool]$missingResult.valid -and [bool]$nullResult.valid -and [bool]$nearValidResult.valid -and $null -eq $missingResult.output.blocked_reason -and $null -eq $nullResult.output.blocked_reason -and $null -eq $nearValidResult.output.blocked_reason -and @($nearValidResult.output.files_changed).Count -eq 1 -and @($nearValidResult.output.commands_run).Count -eq 1 -and [string]$nearValidResult.output.test_result -eq "passed")
        smoke = "artifact-validation-self-test"
        missing_blocked_reason = $missingResult
        null_blocked_reason = $nullResult
        near_valid_artifact = $nearValidResult
    }
}

function Test-GuildArtifactGrounding {
    param(
        [Parameter(Mandatory = $true)]
        [object]$WorkerOutput,
        [Parameter(Mandatory = $true)]
        [object]$Task,
        [string]$Workspace
    )

    $errors = @()
    $taskRequest = ([string]$Task.request).ToLowerInvariant()
    $taskSkill = ([string]$Task.required_skill).ToLowerInvariant()
    $taskType = ([string]$Task.task_type).ToLowerInvariant()
    $text = (Get-GuildWorkerOutputText -WorkerOutput $WorkerOutput -Workspace $Workspace)
    $textLower = $text.ToLowerInvariant()

    if ([bool]$WorkerOutput.ok -and [string]::IsNullOrWhiteSpace($text)) {
        $errors += "Artifact output is empty."
    }
    if ([bool]$WorkerOutput.ok -and $text.Trim().Length -lt 400) {
        $errors += "Artifact output is too short to validate as a scoped deliverable."
    }
    $names = @($WorkerOutput.PSObject.Properties.Name)
    if ($names -contains "file_outputs" -and (Test-ArtifactArrayField -Value $WorkerOutput.file_outputs)) {
        foreach ($item in $WorkerOutput.file_outputs) {
            $itemNames = @($item.PSObject.Properties.Name)
            $content = if ($itemNames -contains "content") { [string]$item.content } else { "" }
            if ($content.ToLowerInvariant().Contains("see file written directly to disk")) {
                $path = if ($itemNames -contains "path") { [string]$item.path } else { "" }
                $hasDurableFile = $false
                if (-not [string]::IsNullOrWhiteSpace($Workspace) -and -not [string]::IsNullOrWhiteSpace($path) -and -not [System.IO.Path]::IsPathRooted($path) -and -not $path.Contains("..")) {
                    $target = Join-Path $Workspace $path
                    if (Test-Path -LiteralPath $target -PathType Leaf) {
                        $existing = Get-Content -LiteralPath $target -Raw
                        $hasDurableFile = ($existing.Trim().Length -ge 400 -and -not $existing.ToLowerInvariant().Contains("see file written directly to disk"))
                    }
                }
                if (-not $hasDurableFile) {
                    $errors += "Artifact file output is a placeholder instead of durable file content."
                }
            }
        }
    }

    $requiredAnchors = @()
    if ($taskRequest.Contains("guild")) { $requiredAnchors += @{ label = "guild"; terms = @("guild") } }
    if ($taskRequest.Contains("hermes")) {
        $hermesTerms = if ($taskRequest.Contains("guild")) { @("hermes", "hermesguildcore", "guild") } else { @("hermes", "hermesguildcore") }
        $requiredAnchors += @{ label = "hermes"; terms = $hermesTerms }
    }
    $workerSpecificRequest = (
        $taskRequest.Contains("worker terminal") -or
        $taskRequest.Contains("worker profile") -or
        $taskRequest.Contains("worker route") -or
        $taskRequest.Contains("wake worker") -or
        $taskRequest.Contains("workers must")
    )
    if ($workerSpecificRequest) { $requiredAnchors += @{ label = "worker"; terms = @("worker", "workers") } }
    if ($taskRequest.Contains("one-hour") -or $taskRequest.Contains("one hour")) {
        $requiredAnchors += @{ label = "one-hour"; terms = @("one-hour", "one hour", "hour", "demo", "guild demo") }
    }
    if ($taskSkill.Contains("requirements")) {
        $requiredAnchors += @{ label = "requirements"; terms = @("requirements", "requirement") }
    } elseif ($taskSkill.Contains("risk")) {
        $requiredAnchors += @{ label = "risk-analysis"; terms = @("risk", "risks", "mismatch", "integration concern") }
    } elseif ($taskSkill.Contains("verification")) {
        $requiredAnchors += @{ label = "verification"; terms = @("verification", "verify", "acceptance evidence") }
    }
    if ($taskType -eq "join_review") {
        $requiredAnchors += @{ label = "join-review"; terms = @("review.md", "final-summary.md", "integration review", "join review") }
    }

    foreach ($anchor in $requiredAnchors) {
        $matched = $false
        foreach ($term in $anchor.terms) {
            if ($textLower.Contains($term)) {
                $matched = $true
                break
            }
        }
        if (-not $matched) {
            $errors += "Artifact is not grounded in required anchor: $($anchor.label)."
        }
    }

    if ($taskRequest.Contains("guild") -and $textLower.Contains("dashboard") -and -not $textLower.Contains("guild")) {
        $errors += "Artifact appears to be a generic dashboard template instead of a Guild-scoped deliverable."
    }
    $hasKnownHermesRouteOrPath = (
        $textLower.Contains("/api/task/retry-blocked") -or
        $textLower.Contains("docs/incubation/guild-dashboard.html") -or
        $textLower.Contains("scripts/guild-dashboard-server.py") -or
        $textLower.Contains("_runtime/flock/worker_team_prototype.py") -or
        $textLower.Contains("scripts/run-guild-worker-agent.ps1") -or
        $textLower.Contains("config/guild/")
    )
    $hasInventedArchitecture = (
        $textLower.Contains("typical application architecture") -or
        $textLower.Contains("src/frontend") -or
        $textLower.Contains("src/backend") -or
        $textLower.Contains("/api/providers/retry-block") -or
        $textLower.Contains("/dashboard/retry-provider-block") -or
        $textLower.Contains("enable_blocked_provider_retry") -or
        $textLower.Contains("task_execution_adapter")
    )
    if (($taskRequest.Contains("config") -or $taskRequest.Contains("route") -or $taskRequest.Contains("provider")) -and ($hasInventedArchitecture -or ($textLower.Contains("conceptual") -and -not $hasKnownHermesRouteOrPath))) {
        $errors += "Artifact appears to be a conceptual architecture map instead of exact HermesGuildCore repo paths."
    }
    if ($taskRequest.Contains("retry provider block") -or $taskRequest.Contains("retry-provider-block")) {
        $knownRetryRoute = $textLower.Contains("/api/task/retry-blocked") -or $textLower.Contains("retry-blocked")
        $knownRetryFile = (
            $textLower.Contains("docs/incubation/guild-dashboard.html") -or
            $textLower.Contains("scripts/guild-dashboard-server.py") -or
            $textLower.Contains("_runtime/flock/worker_team_prototype.py")
        )
        if (-not ($knownRetryRoute -or $knownRetryFile)) {
            $errors += "Artifact does not reference the real Retry provider block route or HermesGuildCore files."
        }
        if ($textLower.Contains("/api/providers/retry-block") -or $textLower.Contains("/dashboard/retry-provider-block") -or $textLower.Contains("enable_blocked_provider_retry") -or $textLower.Contains("task_execution_adapter")) {
            $errors += "Artifact includes invented Retry provider block route or config names."
        }
    }

    return [pscustomobject]@{
        valid = ($errors.Count -eq 0)
        skipped = $false
        blocked_reason = if ($errors.Count -eq 0) { $null } else { "ungrounded_artifact_output" }
        errors = $errors
    }
}

if ($ArtifactValidationSelfTest) {
    $selfTestResult = Invoke-GuildArtifactValidationSelfTest
    if ($Json) { $selfTestResult | ConvertTo-Json -Depth 20 } else { $selfTestResult }
    if (-not [bool]$selfTestResult.ok) { exit 1 }
    return
}

$claimArgs = New-GuildArgs -Tail @(
    "claim-next",
    "--agent-id", $profileData.agent_id,
    "--agent-rank", $profileData.rank,
    "--skills", $profileData.skills,
    "--lease-seconds", $LeaseSeconds,
    "--scan-limit", $ScanLimit,
    "--min-open-age-seconds", $MinOpenAgeSeconds
)
if ($TaskId) {
    $claimArgs += @("--task-id", $TaskId)
}
if ($QuestChainId) {
    $claimArgs += @("--quest-chain-id", $QuestChainId)
}

if (Test-GuildQuestStopRequested -QuestId $QuestChainId) {
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
        reason = "quest_stop_requested"
    }
    if ($Json) { $result | ConvertTo-Json -Depth 20 } else { $result }
    return
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
Add-GuildEventLog -Event "worker_task_claimed" -Details @{
    schema_version = "guild_event_v1"
    layer = "worker-agent"
    phase = "claim"
    severity = "info"
    quest_chain_id = $task.quest_chain_id
    task_id = $task.task_id
    task_title = $task.title
    task_type = $task.task_type
    profile = $Profile
    agent_id = $profileData.agent_id
    adapter = $Adapter
    provider = $Provider
    model = $Model
    input = @{
        source = "blackboard.claim-next"
        quest_chain_id = $task.quest_chain_id
        task_id = $task.task_id
    }
    output = @{
        claimed = $true
        visible_scope = if ($task.task_type -eq "join_review") { "join_review" } else { "task_only" }
    }
}
$taskJson = $task | ConvertTo-Json -Depth 20
$visibleScope = if ($task.task_type -eq "join_review") { "join_review" } else { "task_only" }
$mayCreateFixTask = if ($task.task_type -eq "join_review") { "true" } else { "false" }
$reviewContext = Get-GuildReviewContext -Task $task
$groundingPacket = New-GuildGroundingPacket -Task $task
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

$groundingPacket

Scope rules:
- For visible_scope=task_only, use only this task packet and its explicit dependency context.
- Do not infer or inspect unrelated company/project tasks.
- Do not read secrets.
- Do not edit outside allowed_files.
- If another task appears incompatible, do not silently absorb a contract mismatch; return blocked_reason.
- Tiny compatibility adjustments are acceptable only inside this task's allowed_files and must be reported in the artifact summary.
- For visible_scope=join_review, compare upstream artifacts and report integration mismatches; propose a bounded fix task instead of broad repair.

Quality gates:
- Ground the deliverable in the exact GuildTask request, not a generic app/dashboard template.
- If the task request mentions Guild, Hermes, workers, one-hour demo, or a final review artifact, the file content must explicitly mention the relevant same concept.
- The visible file content must satisfy the assigned module skill: requirements, risk-analysis, verification, or join_review.
- If the context is insufficient to produce a grounded scoped artifact, return ok=false with blocked_reason="insufficient_task_context".

Current GuildTask JSON:
$taskJson

Visible upstream context for this task:
$reviewContext

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
try {
    $adapterRaw = & $adapterScript @adapterArgs
    $adapterExitCode = $LASTEXITCODE
    if ($adapterExitCode -ne 0) {
        throw "Provider adapter failed with exit code $adapterExitCode. Output: $($adapterRaw -join "`n")"
    }
    if (-not $adapterRaw) {
        throw "Provider adapter returned no output (exit code 0)."
    }
} catch {
    Add-GuildEventLog -Event "worker_adapter_invocation_failed" -Details @{
        schema_version = "guild_event_v1"
        layer = "provider-adapter"
        phase = "invoke"
        severity = "error"
        quest_chain_id = $task.quest_chain_id
        task_id = $task.task_id
        task_title = $task.title
        profile = $Profile
        agent_id = $profileData.agent_id
        adapter = $Adapter
        provider = $Provider
        model = $Model
        error = $_.Exception.Message
        input = @{
            source = "worker-agent.prompt-packet"
            task_id = $task.task_id
            adapter = $Adapter
        }
        output = @{
            ok = $false
            blocked_reason = "provider_failed"
        }
    }
    throw
}
try {
    $adapterResult = $adapterRaw | ConvertFrom-Json
} catch {
    Add-GuildEventLog -Event "worker_adapter_result_parse_failed" -Details @{
        schema_version = "guild_event_v1"
        layer = "provider-adapter"
        phase = "parse"
        severity = "error"
        quest_chain_id = $task.quest_chain_id
        task_id = $task.task_id
        task_title = $task.title
        profile = $Profile
        agent_id = $profileData.agent_id
        adapter = $Adapter
        provider = $Provider
        model = $Model
        error = $_.Exception.Message
        input = @{
            source = "provider-adapter.stdout"
            task_id = $task.task_id
        }
        output = @{
            ok = $false
            blocked_reason = "invalid_adapter_output"
        }
    }
    throw
}

if (Test-GuildQuestStopRequested -QuestId ([string]$task.quest_chain_id)) {
    $result = [pscustomobject]@{
        ok = $false
        claimed = $true
        profile = $Profile
        adapter = $Adapter
        provider = $Provider
        model = $Model
        agent_id = $profileData.agent_id
        task_id = $task.task_id
        task_title = $task.title
        quest_chain_id = $task.quest_chain_id
        blocked_reason = "quest_stop_requested"
        artifact = $null
        status_update = $null
        unlock = $null
        adapter_result = $adapterResult
    }
    if ($Json) { $result | ConvertTo-Json -Depth 30 } else { $result }
    return
}

$artifactValidation = Test-GuildArtifactOutput -AdapterResult $adapterResult
$workerOutput = $artifactValidation.output
if ($workerOutput) {
    Normalize-GuildWorkerOutputPaths -WorkerOutput $workerOutput -AllowedFiles ([string]$task.allowed_files)
}
$groundingValidation = if ($workerOutput -and [bool]$artifactValidation.valid) {
    Test-GuildArtifactGrounding -WorkerOutput $workerOutput -Task $task -Workspace $workspace
} else {
    [pscustomobject]@{
        valid = $false
        skipped = $true
        blocked_reason = "invalid_adapter_output"
        errors = @("Skipped grounding validation because artifact validation failed.")
    }
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
$fileOutputScopeValidation = if ($workerOutput) {
    Test-GuildFileOutputsWithinAllowedScope -WorkerOutput $workerOutput -AllowedFiles ([string]$task.allowed_files)
} else {
    [pscustomobject]@{
        valid = $false
        blocked_reason = "invalid_adapter_output"
        errors = @("Adapter output did not produce file_outputs.")
    }
}
$fileWrite = if ($workerOutput -and [bool]$artifactValidation.valid -and [bool]$groundingValidation.valid -and [bool]$scopeValidation.valid -and [bool]$fileOutputScopeValidation.valid) {
    Write-GuildWorkerFileOutputs -WorkerOutput $workerOutput -Workspace $workspace
} else {
    [pscustomobject]@{
        ok = $false
        skipped = $true
        written = @()
        errors = @("Skipped file output write because artifact, grounding, scope, or file output scope validation failed.")
    }
}
$artifactOk = [bool]$adapterResult.ok `
    -and -not $adapterResult.blocked_reason `
    -and [bool]$artifactValidation.valid `
    -and [bool]$groundingValidation.valid `
    -and [bool]$scopeValidation.valid `
    -and [bool]$fileOutputScopeValidation.valid `
    -and [bool]$fileWrite.ok `
    -and [bool]$workerOutput.ok `
    -and -not $workerOutput.blocked_reason

$effectiveBlockedReason = if ($adapterResult.blocked_reason) {
    $adapterResult.blocked_reason
} elseif (-not $artifactValidation.valid) {
    $artifactValidation.blocked_reason
} elseif ($groundingValidation -and -not $groundingValidation.valid) {
    $groundingValidation.blocked_reason
} elseif ($scopeValidation -and -not $scopeValidation.valid) {
    $scopeValidation.blocked_reason
} elseif ($fileOutputScopeValidation -and -not $fileOutputScopeValidation.valid) {
    $fileOutputScopeValidation.blocked_reason
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
    artifact_grounding_validation = $groundingValidation
    file_scope_validation = $scopeValidation
    file_output_scope_validation = $fileOutputScopeValidation
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
} elseif (Test-RetryableInfrastructureBlockedReason -Reason $effectiveBlockedReason) {
    "agent_$($profileData.agent_id)_blocked_$($task.task_id)"
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
    if ($effectiveBlockedReason -eq "needs_info" -or (Test-RetryableInfrastructureBlockedReason -Reason $effectiveBlockedReason)) {
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

$finalEvent = if ($artifactOk) {
    "worker_task_done"
} elseif ($statusUpdate -and [string]$statusUpdate.status -eq "blocked") {
    "worker_task_blocked"
} else {
    "worker_task_failed"
}
Add-GuildEventLog -Event $finalEvent -Details @{
    schema_version = "guild_event_v1"
    layer = "worker-agent"
    phase = "complete"
    severity = if ($artifactOk) { "info" } elseif ($statusUpdate -and [string]$statusUpdate.status -eq "blocked") { "warn" } else { "error" }
    quest_chain_id = $task.quest_chain_id
    task_id = $task.task_id
    task_title = $task.title
    task_type = $task.task_type
    profile = $Profile
    agent_id = $profileData.agent_id
    adapter = $Adapter
    provider = $Provider
    model = $Model
    status = if ($statusUpdate -and $statusUpdate.status) { $statusUpdate.status } elseif ($artifactOk) { "done" } else { "failed" }
    blocked_reason = $effectiveBlockedReason
    artifact_validation_valid = [bool]$artifactValidation.valid
    grounding_valid = [bool]$groundingValidation.valid
    file_scope_valid = [bool]$scopeValidation.valid
    file_output_scope_valid = [bool]$fileOutputScopeValidation.valid
    file_write_ok = [bool]$fileWrite.ok
    payload_path = (Resolve-Path -LiteralPath $payloadPath).Path.Replace($workspace, "").TrimStart("\")
    input = @{
        source = "provider-adapter.result"
        task_id = $task.task_id
        adapter = $Adapter
        provider = $Provider
        model = $Model
    }
    output = @{
        artifact_ok = $artifactOk
        status = if ($statusUpdate -and $statusUpdate.status) { $statusUpdate.status } elseif ($artifactOk) { "done" } else { "failed" }
        blocked_reason = $effectiveBlockedReason
        payload_path = (Resolve-Path -LiteralPath $payloadPath).Path.Replace($workspace, "").TrimStart("\")
    }
}

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

