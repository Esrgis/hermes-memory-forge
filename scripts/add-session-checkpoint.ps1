[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Summary,

    [ValidateSet("decision", "code_change", "test", "bug", "audit", "user_preference", "status", "handoff", "note")]
    [string]$Kind = "note",

    [string[]]$Evidence = @(),

    [string[]]$Files = @(),

    [string[]]$NextAction = @(),

    [string[]]$Risk = @(),

    [ValidateSet("none", "low", "medium", "high")]
    [string]$MemoryValue = "medium",

    [ValidateSet("codex", "hermes", "manual")]
    [string]$Source = "codex",

    [string]$CheckpointDir = "_runtime\session-checkpoints",

    [switch]$DryRun,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][object]$Value)

    if ($Json) {
        $Value | ConvertTo-Json -Depth 8
        return
    }
    $Value
}

function Assert-CleanText {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [AllowEmptyString()][string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }
    if ($Value.Length -gt 2000) {
        throw "$Label is too long for a distilled checkpoint."
    }
    $secretLikePatterns = @(
        'sk-[A-Za-z0-9_\-]{16,}',
        'ghp_[A-Za-z0-9_]{16,}',
        'github_pat_[A-Za-z0-9_]{16,}',
        'xox[baprs]-[A-Za-z0-9\-]{16,}',
        '(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S{8,}'
    )
    foreach ($pattern in $secretLikePatterns) {
        if ($Value -match $pattern) {
            throw "$Label looks like it may contain a secret. Refusing checkpoint."
        }
    }
}

function Normalize-Items {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [string[]]$Items,
        [int]$Limit = 12
    )

    $clean = @()
    foreach ($item in $Items) {
        $value = ([string]$item).Trim()
        if (-not $value) {
            continue
        }
        Assert-CleanText -Label $Label -Value $value
        $clean += $value
        if ($clean.Count -ge $Limit) {
            break
        }
    }
    return $clean
}

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$checkpointRoot = if ([System.IO.Path]::IsPathRooted($CheckpointDir)) {
    $CheckpointDir
} else {
    Join-Path $workspace $CheckpointDir
}

$summaryText = $Summary.Trim()
if (-not $summaryText) {
    throw "Summary is required."
}
Assert-CleanText -Label "Summary" -Value $summaryText

$now = Get-Date
$idStamp = $now.ToString("yyyyMMdd-HHmmss-fff")
$id = "$idStamp-$Source-$Kind"
$path = Join-Path $checkpointRoot "$id.json"

$event = [ordered]@{
    schema_version = "session_checkpoint_event_v1"
    id = $id
    status = "pending"
    created_at = $now.ToUniversalTime().ToString("o")
    local_time = $now.ToString("yyyy-MM-dd HH:mm:ss")
    source = $Source
    kind = $Kind
    memory_value = $MemoryValue
    summary = $summaryText
    evidence = @(Normalize-Items -Label "Evidence" -Items $Evidence -Limit 12)
    files = @(Normalize-Items -Label "Files" -Items $Files -Limit 20)
    next_action = @(Normalize-Items -Label "NextAction" -Items $NextAction -Limit 8)
    risk = @(Normalize-Items -Label "Risk" -Items $Risk -Limit 8)
}

if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $checkpointRoot | Out-Null
    $event | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
}

Write-Result ([pscustomobject]@{
    ok = $true
    dry_run = [bool]$DryRun
    checkpoint = $event
    path = $path
})
