[CmdletBinding(DefaultParameterSetName = "DryRun")]
param(
    [string]$CheckpointDir = "_runtime\session-checkpoints",

    [int]$MaxEvents = 20,

    [switch]$IncludeLow,

    [ValidateSet("codex", "hermes", "manual")]
    [string]$Source = "codex",

    [Parameter(ParameterSetName = "DryRun")]
    [switch]$DryRun,

    [Parameter(ParameterSetName = "Apply")]
    [switch]$Apply,

    [switch]$ShowCandidate,

    [switch]$Json,

    [switch]$JsonCompact,

    [switch]$SummaryOnly,

    [int]$ChangedPathLimit = 20
)

$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][object]$Value)

    if ($Json -or $JsonCompact) {
        $Value | ConvertTo-Json -Depth 10
        return
    }
    $Value
}

function Convert-ToArray {
    param($Value)

    if ($null -eq $Value) {
        return @()
    }
    if ($Value -is [string]) {
        if ([string]::IsNullOrWhiteSpace($Value)) {
            return @()
        }
        return @($Value)
    }
    return @($Value)
}

function Format-CheckpointLine {
    param([Parameter(Mandatory = $true)]$Event)

    $time = ""
    if ($Event.local_time) {
        try {
            $time = ([datetime]$Event.local_time).ToString("HH:mm")
        } catch {
            $time = ([string]$Event.local_time).Substring(0, [Math]::Min(5, ([string]$Event.local_time).Length))
        }
    }
    if (-not $time) {
        $time = "time?"
    }
    return "{0} [{1}] {2}" -f $time, $Event.kind, ([string]$Event.summary).Trim()
}

function Get-UniqueCleanItems {
    param(
        [object[]]$Events,
        [string]$Property,
        [int]$Limit = 10
    )

    $seen = @{}
    $items = @()
    foreach ($event in $Events) {
        foreach ($item in (Convert-ToArray $event.$Property)) {
            $value = ([string]$item).Trim()
            if (-not $value) {
                continue
            }
            $key = $value.ToLowerInvariant()
            if ($seen.ContainsKey($key)) {
                continue
            }
            $seen[$key] = $true
            $items += $value
            if ($items.Count -ge $Limit) {
                return $items
            }
        }
    }
    return $items
}

function Invoke-GitText {
    param([string[]]$Arguments)
    try {
        $output = & git @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) {
            return @()
        }
        return @($output)
    } catch {
        return @()
    }
}

function Test-TextGuard {
    param(
        [string]$Text,
        [string]$Kind
    )

    $patterns = if ($Kind -eq "secret") {
        @(
            'sk-[A-Za-z0-9_\-]{16,}',
            'ghp_[A-Za-z0-9_]{16,}',
            'github_pat_[A-Za-z0-9_]{16,}',
            'xox[baprs]-[A-Za-z0-9\-]{16,}',
            '(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S{8,}'
        )
    } else {
        @(
            '(?im)^\s*(user|assistant|system|tool):\s+',
            '(?i)<\|im_(start|end)\|>',
            '(?i)"role"\s*:\s*"(user|assistant|system|tool)"'
        )
    }

    foreach ($pattern in $patterns) {
        if ($Text -match $pattern) {
            return "failed"
        }
    }
    return "passed"
}

function Convert-StatusLineToPath {
    param([string]$Line)

    if ([string]::IsNullOrWhiteSpace($Line)) {
        return ""
    }
    $value = $Line
    if ($value.Length -gt 3) {
        $value = $value.Substring(3)
    }
    if ($value -match ' -> ') {
        $value = ($value -split ' -> ')[-1]
    }
    return $value.Trim().Trim('"')
}

function New-DirtySnapshot {
    param([int]$Limit)

    $gitStatus = @(Invoke-GitText -Arguments @("status", "--porcelain=v1"))
    $tracked = @($gitStatus | Where-Object { $_ -match '^\s*[MADRCU]{1,2}\s+' })
    $untracked = @($gitStatus | Where-Object { $_ -match '^\?\?\s+' })
    $examples = @(
        $gitStatus |
            ForEach-Object { Convert-StatusLineToPath -Line $_ } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -First $Limit
    )

    return [pscustomobject]@{
        tracked_modified = $tracked.Count
        untracked = $untracked.Count
        examples = $examples
    }
}

function Write-FlushPreviewFile {
    param(
        [Parameter(Mandatory = $true)]$MemoryResult,
        [Parameter(Mandatory = $true)]$DirtySnapshot
    )

    $previewDir = Join-Path $checkpointRoot "flush-preview"
    New-Item -ItemType Directory -Force -Path $previewDir | Out-Null
    $previewPath = Join-Path $previewDir "latest.md"
    $lines = @(
        "# Session Checkpoint Flush Preview",
        "",
        "Generated: $((Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))",
        "",
        "## Targets",
        "",
        "- $($MemoryResult.would_append_daily)",
        "- $($MemoryResult.would_write_current_state)",
        "",
        "## Guards",
        "",
        "- secret_scan: $(Test-TextGuard -Text (($MemoryResult.candidate, $MemoryResult.current_state) -join "`n") -Kind "secret")",
        "- raw_log_scan: $(Test-TextGuard -Text (($MemoryResult.candidate, $MemoryResult.current_state) -join "`n") -Kind "raw_log")",
        "",
        "## Dirty Snapshot",
        "",
        "- tracked_modified: $($DirtySnapshot.tracked_modified)",
        "- untracked: $($DirtySnapshot.untracked)",
        "",
        "## Candidate Daily Note",
        "",
        $MemoryResult.candidate,
        "",
        "## Candidate Current State",
        "",
        $MemoryResult.current_state
    )
    $lines | Set-Content -LiteralPath $previewPath -Encoding UTF8
    return $previewPath
}

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$checkpointRoot = if ([System.IO.Path]::IsPathRooted($CheckpointDir)) {
    $CheckpointDir
} else {
    Join-Path $workspace $CheckpointDir
}
$closeMemory = Join-Path $workspace "scripts\close-session-memory.ps1"
if (-not (Test-Path -LiteralPath $closeMemory -PathType Leaf)) {
    throw "Missing close-session-memory route: $closeMemory"
}

if (-not (Test-Path -LiteralPath $checkpointRoot -PathType Container)) {
    Write-Result ([pscustomobject]@{
        ok = $true
        mode = if ($Apply) { "apply" } else { "dry_run" }
        checkpoint_dir = $checkpointRoot
        pending_count = 0
        promoted_count = 0
        message = "No checkpoint directory."
    })
    exit 0
}

$files = @(Get-ChildItem -LiteralPath $checkpointRoot -Filter "*.json" -File | Sort-Object Name)
$pending = @()
foreach ($file in $files) {
    try {
        $event = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
    } catch {
        continue
    }
    if ($event.schema_version -ne "session_checkpoint_event_v1") {
        continue
    }
    if (($event.status -as [string]) -ne "pending") {
        continue
    }
    $event | Add-Member -NotePropertyName checkpoint_path -NotePropertyValue $file.FullName -Force
    $pending += $event
}

if ($pending.Count -eq 0) {
    Write-Result ([pscustomobject]@{
        ok = $true
        mode = if ($Apply) { "apply" } else { "dry_run" }
        checkpoint_dir = $checkpointRoot
        pending_count = 0
        promoted_count = 0
        message = "No pending checkpoints."
    })
    exit 0
}

$selected = @($pending | Select-Object -First $MaxEvents)
$promoted = @(
    $selected | Where-Object {
        $_.memory_value -in @("medium", "high") -or ($IncludeLow -and $_.memory_value -eq "low")
    }
)
$skipped = @($selected | Where-Object { $promoted -notcontains $_ })

if ($promoted.Count -eq 0) {
    $summary = "Checkpoint queue flush: no promotable events; skipped $($skipped.Count) low/noise checkpoint(s)."
    $next = @("Continue collecting checkpoint events; promote only medium/high value distilled events.")
    $risk = @("Do not promote raw logs or low-value noise into Obsidian memory.")
} else {
    $lines = @($promoted | ForEach-Object { Format-CheckpointLine -Event $_ })
    $summary = "Checkpoint queue flush: " + ($lines -join "; ")
    $next = @(Get-UniqueCleanItems -Events $promoted -Property "next_action" -Limit 10)
    if ($next.Count -eq 0) {
        $next = @("Continue from the latest checkpointed state.")
    }
    $risk = @(Get-UniqueCleanItems -Events $promoted -Property "risk" -Limit 10)
    if ($risk.Count -eq 0) {
        $risk = @("Do not store raw chat logs or secrets as memory.")
    }
}

$memoryArgs = @{
    Summary = $summary
    NextAction = $next
    Risk = $risk
    Source = $Source
}

if ($Apply) {
    $memoryResult = & $closeMemory @memoryArgs -Apply
    $flushedAt = (Get-Date).ToUniversalTime().ToString("o")
    foreach ($event in $selected) {
        $path = [string]$event.checkpoint_path
        if (-not $path) {
            continue
        }
        $event.PSObject.Properties.Remove("checkpoint_path")
        $event.status = "flushed"
        $event | Add-Member -NotePropertyName flushed_at -NotePropertyValue $flushedAt -Force
        $event | Add-Member -NotePropertyName promoted -NotePropertyValue ($promoted -contains $event) -Force
        $event | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
    }
    Write-Result ([pscustomobject]@{
        ok = $true
        mode = "apply"
        checkpoint_dir = $checkpointRoot
        pending_count = $pending.Count
        flushed_count = $selected.Count
        promoted_count = $promoted.Count
        skipped_count = $skipped.Count
        summary = $summary
        memory_result = $memoryResult
    })
    exit 0
}

$memoryResult = & $closeMemory @memoryArgs -DryRun
$dirtySnapshot = New-DirtySnapshot -Limit $ChangedPathLimit
$guardText = (($memoryResult.candidate, $memoryResult.current_state) -join "`n")
$secretScan = Test-TextGuard -Text $guardText -Kind "secret"
$rawLogScan = Test-TextGuard -Text $guardText -Kind "raw_log"
$previewPath = Write-FlushPreviewFile -MemoryResult $memoryResult -DirtySnapshot $dirtySnapshot

$result = [ordered]@{
    ok = $true
    mode = if ($ShowCandidate) { "dry_run" } else { "dry_run_compact" }
    checkpoint_dir = $checkpointRoot
    pending_count = $pending.Count
    would_flush_count = $selected.Count
    promoted_count = $promoted.Count
    skipped_count = $skipped.Count
    targets = @($memoryResult.would_append_daily, $memoryResult.would_write_current_state)
    promoted = @($promoted | ForEach-Object { $_.summary })
    skipped = @($skipped | ForEach-Object { $_.summary })
    guards = [ordered]@{
        secret_scan = $secretScan
        raw_log_scan = $rawLogScan
    }
    candidate_written = $previewPath
    dirty_snapshot = $dirtySnapshot
}

if ($ShowCandidate -and -not $SummaryOnly -and -not $JsonCompact) {
    $result.promoted_details = @($promoted | ForEach-Object {
        [pscustomobject]@{
            id = $_.id
            local_time = $_.local_time
            kind = $_.kind
            memory_value = $_.memory_value
            summary = $_.summary
        }
    })
    $result.skipped_details = @($skipped | ForEach-Object {
        [pscustomobject]@{
            id = $_.id
            kind = $_.kind
            memory_value = $_.memory_value
            summary = $_.summary
        }
    })
    $result.candidate_daily_note = $memoryResult.candidate
    $result.candidate_current_state = $memoryResult.current_state
    $result.changed_paths_full = @(Invoke-GitText -Arguments @("status", "--porcelain=v1"))
    $result.memory_dry_run = $memoryResult
}

Write-Result ([pscustomobject]$result)
