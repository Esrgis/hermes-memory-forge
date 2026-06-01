[CmdletBinding()]
param(
    [string]$ConfigPath = "config\runtime-paths.json",

    [int]$OlderThanDays = 1,

    [switch]$MeasureSize
)

$ErrorActionPreference = "Stop"

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$configFullPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath
} else {
    Join-Path $workspace $ConfigPath
}

if (-not (Test-Path -LiteralPath $configFullPath -PathType Leaf)) {
    throw "Missing runtime path config: $configFullPath"
}

function Expand-HermesPath {
    param([Parameter(Mandatory = $true)][string]$Value)

    $expanded = [Environment]::ExpandEnvironmentVariables($Value)
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        return $expanded
    }
    return Join-Path $workspace $expanded
}

function Get-ScopedSize {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return $null
    }
    $item = Get-Item -LiteralPath $LiteralPath -Force
    if (-not $item.PSIsContainer) {
        return $item.Length
    }
    $bytes = 0
    Get-ChildItem -LiteralPath $LiteralPath -Force -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { $bytes += $_.Length }
    return $bytes
}

function New-Candidate {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item,
        [Parameter(Mandatory = $true)][string]$Bucket,
        [Parameter(Mandatory = $true)][string]$Reason
    )

    [pscustomobject]@{
        bucket = $Bucket
        path = $Item.FullName
        item_type = if ($Item.PSIsContainer) { "directory" } else { "file" }
        last_write_time = $Item.LastWriteTime
        age_days = [Math]::Round(((Get-Date) - $Item.LastWriteTime).TotalDays, 2)
        bytes = if ($MeasureSize) { Get-ScopedSize -LiteralPath $Item.FullName } else { $null }
        cleanup_policy = "dry_run_only"
        reason = $Reason
    }
}

$cutoff = (Get-Date).AddDays(-1 * [Math]::Max(0, $OlderThanDays))
$config = Get-Content -LiteralPath $configFullPath -Raw | ConvertFrom-Json
$paths = @{}
foreach ($entry in $config.paths) {
    $paths[[string]$entry.id] = Expand-HermesPath -Value ([string]$entry.path)
}

$candidates = @()

$runtimeRoot = $paths["workspace_runtime"]
if ($runtimeRoot -and (Test-Path -LiteralPath $runtimeRoot -PathType Container)) {
    $safeRuntimeChildren = @(
        "dashboard",
        "guild-worker-agent",
        "guild-provider-adapters",
        "content-factory",
        "content-factory-demo"
    )
    foreach ($name in $safeRuntimeChildren) {
        $path = Join-Path $runtimeRoot $name
        if (Test-Path -LiteralPath $path) {
            $item = Get-Item -LiteralPath $path -Force
            if ($item.LastWriteTime -lt $cutoff) {
                $candidates += New-Candidate -Item $item -Bucket "_runtime" -Reason "Known ignored runtime folder older than threshold."
            }
        }
    }
}

$questRoot = $paths["quest_artifacts"]
if ($questRoot -and (Test-Path -LiteralPath $questRoot -PathType Container)) {
    Get-ChildItem -LiteralPath $questRoot -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "quest-*" -and $_.LastWriteTime -lt $cutoff } |
        ForEach-Object {
            $candidates += New-Candidate -Item $_ -Bucket "guild-workspaces" -Reason "Old ignored quest artifact folder."
        }
}

$tempPattern = $paths["demo_temp_sqlite"]
if ($tempPattern) {
    Get-ChildItem -Path $tempPattern -Force -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object {
            $candidates += New-Candidate -Item $_ -Bucket "temp-demo-sqlite" -Reason "Temporary demo SQLite file."
        }
}

$summary = [pscustomobject]@{
    ok = $true
    mode = "dry_run_only"
    workspace = $workspace
    older_than_days = $OlderThanDays
    measure_size = [bool]$MeasureSize
    candidate_count = $candidates.Count
    total_bytes = if ($MeasureSize) { ($candidates | Measure-Object -Property bytes -Sum).Sum } else { $null }
    skipped = @(
        "_obsidian_vault",
        "_hermes",
        "_runtime/provider-secrets.local.ps1",
        "%LOCALAPPDATA%/hermes/*.sqlite",
        ".git"
    )
    candidates = @($candidates | Sort-Object bucket, last_write_time, path)
}

$summary
