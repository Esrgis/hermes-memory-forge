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

    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][object]$Value)

    if ($Json) {
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
Write-Result ([pscustomobject]@{
    ok = $true
    mode = "dry_run"
    checkpoint_dir = $checkpointRoot
    pending_count = $pending.Count
    would_flush_count = $selected.Count
    promoted_count = $promoted.Count
    skipped_count = $skipped.Count
    promoted = @($promoted | ForEach-Object {
        [pscustomobject]@{
            id = $_.id
            local_time = $_.local_time
            kind = $_.kind
            memory_value = $_.memory_value
            summary = $_.summary
        }
    })
    skipped = @($skipped | ForEach-Object {
        [pscustomobject]@{
            id = $_.id
            kind = $_.kind
            memory_value = $_.memory_value
            summary = $_.summary
        }
    })
    memory_dry_run = $memoryResult
})
